#!/usr/bin/env python3

# process_replies.py

import imaplib
import email
from email.header import decode_header
import os
import re
import datetime
from dateutil import parser as date_parser  # Requires the python-dateutil package
from db_connection import get_db_connection
from dotenv import load_dotenv

# Load environment variables
load_dotenv(/home/llama/llama_tasks/.env)

def process_emails():
    imap_server = os.getenv('IMAP_SERVER')
    imap_port = int(os.getenv('IMAP_PORT'))
    email_address = os.getenv('EMAIL_ADDRESS')
    email_password = os.getenv('EMAIL_PASSWORD')

    if not all([imap_server, imap_port, email_address, email_password]):
        print("IMAP configuration is incomplete in the .env file.")
        return

    try:
        mail = imaplib.IMAP4_SSL(imap_server, imap_port)
        mail.login(email_address, email_password)
    except Exception as e:
        print(f"Failed to connect to the IMAP server: {e}")
        return

    try:
        mail.select("inbox")

        # Search for unread emails
        status, messages = mail.search(None, '(UNSEEN)')
        email_ids = messages[0].split()

        if not email_ids:
            print("No new emails to process.")
            return

        for email_id in email_ids:
            status, msg_data = mail.fetch(email_id, '(RFC822)')
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    # Parse the email content
                    msg = email.message_from_bytes(response_part[1])

                    # Decode email subject
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding if encoding else 'utf-8')

                    # Remove common reply prefixes
                    subject = re.sub(r'^(Re:|Fwd:)\s*', '', subject, flags=re.IGNORECASE).strip()

                    # Get sender's email
                    from_header = msg.get("From")
                    sender_email = email.utils.parseaddr(from_header)[1]

                    # Get the email body
                    body = get_email_body(msg)

                    # Process the email content
                    process_email_content(sender_email, subject, body)

            # Mark email as seen
            mail.store(email_id, '+FLAGS', '\\Seen')

    except Exception as e:
        print(f"An error occurred while processing emails: {e}")
    finally:
        mail.logout()

def get_email_body(msg):
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            if content_type == "text/plain" and "attachment" not in content_disposition:
                charset = part.get_content_charset()
                payload = part.get_payload(decode=True)
                if payload:
                    if charset:
                        body += payload.decode(charset, errors='replace')
                    else:
                        body += payload.decode(errors='replace')
    else:
        charset = msg.get_content_charset()
        payload = msg.get_payload(decode=True)
        if payload:
            if charset:
                body = payload.decode(charset, errors='replace')
            else:
                body = payload.decode(errors='replace')
    return body

def process_email_content(sender_email, subject, body):
    # Assuming the subject line is 'Task Reminder - Tasks Due'
    if subject.lower() != 'task reminder - tasks due':
        print(f"Email from {sender_email} has an unexpected subject: {subject}")
        return

    # Extract completion lines from the email body
    # Only consider the first part to avoid quoted content
    lines = body.strip().split('\n')
    new_content_lines = []
    for line in lines:
        line = line.strip()
        # Stop processing if we hit a quoted line
        if line.startswith('>') or line.lower().startswith('on ') or line.lower().startswith('from:'):
            break
        new_content_lines.append(line)

    # Process each completion line
    for line in new_content_lines:
        # Adjusted regex to handle extra whitespace and case-insensitive matching
        match = re.match(r'Completed:\s*(.+?)\s+on\s+(.+)', line, re.IGNORECASE)
        if match:
            task_name = match.group(1).strip()
            completion_date_str = match.group(2).strip()

            # Try parsing the date with multiple formats
            completion_date = parse_date(completion_date_str)
            if completion_date:
                update_task_completion(sender_email, task_name, completion_date)
            else:
                print(f"Invalid date format in line: {line}")
        else:
            print(f"Unrecognized line format: {line}")

def parse_date(date_str):
    # List of date formats to try
    date_formats = [
        '%Y-%m-%d',      # 2023-10-24
        '%m/%d/%Y',      # 10/24/2023
        '%d-%m-%Y',      # 24-10-2023
        '%B %d, %Y',     # October 24, 2023
        '%b %d, %Y',     # Oct 24, 2023
        '%d %B %Y',      # 24 October 2023
        '%d %b %Y',      # 24 Oct 2023
    ]
    for fmt in date_formats:
        try:
            return datetime.datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    # If none of the formats match, try using dateutil.parser
    try:
        return date_parser.parse(date_str, fuzzy=True).date()
    except (ValueError, TypeError):
        return None

def update_task_completion(sender_email, task_name, completion_date):
    connection = get_db_connection()
    if not connection:
        print("Cannot proceed without a database connection.")
        return
    cursor = connection.cursor()
    try:
        # Get person_id from email
        cursor.execute("SELECT person_id FROM people WHERE email = %s", (sender_email,))
        person = cursor.fetchone()
        if not person:
            print(f"No person found with email {sender_email}")
            return
        person_id = person['person_id']

        # Get task_id and recurrence_period
        cursor.execute("SELECT task_id, recurrence_period FROM tasks WHERE task_name ILIKE %s", (task_name,))
        task = cursor.fetchone()
        if not task:
            print(f"No task found with name '{task_name}'")
            return
        task_id = task['task_id']
        recurrence_period = task['recurrence_period']

        # Ensure recurrence_period is an integer number of days
        if isinstance(recurrence_period, datetime.timedelta):
            recurrence_days = recurrence_period.days
        else:
            # If recurrence_period is stored as an interval or integer
            recurrence_days = int(recurrence_period)

        # Calculate next due date
        next_due_date = completion_date + datetime.timedelta(days=recurrence_days)

        # Check if a record already exists
        cursor.execute("SELECT * FROM task_completion WHERE person_id = %s AND task_id = %s", (person_id, task_id))
        existing_record = cursor.fetchone()
        if existing_record:
            # Update existing record
            cursor.execute("""
                UPDATE task_completion
                SET completion_date = %s, next_due_date = %s
                WHERE person_id = %s AND task_id = %s
            """, (completion_date, next_due_date, person_id, task_id))
        else:
            # Insert new record
            cursor.execute("""
                INSERT INTO task_completion (person_id, task_id, completion_date, next_due_date)
                VALUES (%s, %s, %s, %s)
            """, (person_id, task_id, completion_date, next_due_date))
        connection.commit()
        print(f"Updated task completion for {sender_email} - {task_name}")
    except Exception as e:
        print(f"Failed to update task completion: {e}")
    finally:
        connection.close()

if __name__ == '__main__':
    process_emails()
