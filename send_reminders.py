# send_reminders.py

import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from db_connection import get_db_connection
import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_due_tasks():
    connection = get_db_connection()
    if not connection:
        print("Cannot proceed without a database connection.")
        return []
    
    cursor = connection.cursor()
    
    today = datetime.date.today()
    
    query = """
    SELECT
        p.person_id,
        p.name,
        p.email,
        t.task_id,
        t.task_name,
        tc.next_due_date
    FROM
        task_completion tc
    JOIN
        people p ON tc.person_id = p.person_id
    JOIN
        tasks t ON tc.task_id = t.task_id
    WHERE
        tc.next_due_date <= %s
    ORDER BY
        p.person_id;
    """
    
    cursor.execute(query, (today,))
    tasks_due = cursor.fetchall()
    connection.close()
    return tasks_due

def group_tasks_by_person(tasks_due):
    tasks_by_person = {}
    for task in tasks_due:
        person_id = task['person_id']
        if person_id not in tasks_by_person:
            tasks_by_person[person_id] = {
                'name': task['name'],
                'email': task['email'],
                'tasks': []
            }
        tasks_by_person[person_id]['tasks'].append({
            'task_id': task['task_id'],
            'task_name': task['task_name'],
            'next_due_date': task['next_due_date']
        })
    return tasks_by_person

def send_emails(tasks_by_person):
    smtp_server = os.getenv('SMTP_SERVER')
    smtp_port = int(os.getenv('SMTP_PORT'))
    email_address = os.getenv('EMAIL_ADDRESS')
    email_password = os.getenv('EMAIL_PASSWORD')

    if not all([smtp_server, smtp_port, email_address, email_password]):
        print("SMTP configuration is incomplete in the .env file.")
        return

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(email_address, email_password)
    except Exception as e:
        print(f"Failed to connect to the SMTP server: {e}")
        return

    for person in tasks_by_person.values():
        msg = MIMEMultipart()
        msg['From'] = email_address
        msg['To'] = person['email']
        msg['Subject'] = 'Task Reminder - Tasks Due'

        # Build the email body with the list of tasks
        task_list = ''
        for task in person['tasks']:
            task_list += f"- {task['task_name']} (Due Date: {task['next_due_date'].strftime('%Y-%m-%d')})\n"

        body = f"""Dear {person['name']},

This is a reminder that you have the following tasks due:

{task_list}

To report completion of these tasks, please reply to this email and include the lines:

Completed: [Task Name] on YYYY-MM-DD

Please replace [Task Name] with the actual task name and YYYY-MM-DD with the date you completed the task. You can report multiple tasks in the same reply by including multiple lines.

Example:

Completed: Fire Safety Training on 2023-10-24
Completed: Data Privacy Compliance on 2023-10-25

Thank you for your attention to these tasks.

Best regards,
Task Management System
"""

        msg.attach(MIMEText(body, 'plain'))

        try:
            server.send_message(msg)
            print(f"Email sent to {person['name']} at {person['email']}")
        except Exception as e:
            print(f"Failed to send email to {person['email']}: {e}")

    server.quit()

if __name__ == '__main__':
    tasks_due = get_due_tasks()
    if tasks_due:
        tasks_by_person = group_tasks_by_person(tasks_due)
        send_emails(tasks_by_person)
    else:
        print("No tasks due at this time.")
