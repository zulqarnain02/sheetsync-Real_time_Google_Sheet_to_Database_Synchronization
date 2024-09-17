import gspread
import MySQLdb
from django.conf import settings
from oauth2client.service_account import ServiceAccountCredentials
from django.http import JsonResponse
from django.shortcuts import render, redirect
from googleapiclient.discovery import build
from django.db import connection
from django.views.decorators.csrf import csrf_exempt
import requests
import logging

logger = logging.getLogger(__name__)
# Authenticate Google Sheets API
def authenticate_google_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials = ServiceAccountCredentials.from_json_keyfile_name(settings.GOOGLE_SHEETS_CREDENTIALS_PATH, scope)
    client = gspread.authorize(credentials)
    return client

# View to handle form submission and sync
def sync_google_sheet(request):
    if request.method == 'POST':
        sheet_id = request.POST.get('sheet_id')

        # Open the Google Sheet by ID
        client = authenticate_google_sheets()
        spreadsheet = client.open_by_key(sheet_id)

        # Fetch the title of the entire spreadsheet (document)
        spreadsheet_title = spreadsheet.title
        print(f"Google Sheet ID: {sheet_id}")
        print(f"Spreadsheet title (used as table name): {spreadsheet_title}")

        # Get all worksheets in the spreadsheet and print their names for debugging
        sheet_list = spreadsheet.worksheets()

        # Select the first sheet by default (or you can specify another logic if needed)
        sheet = sheet_list[0]  # Using the first worksheet

        # Check if the spreadsheet title exists as a table in the MySQL database
        with connection.cursor() as cursor:
            cursor.execute("SHOW TABLES LIKE %s", [spreadsheet_title])
            result = cursor.fetchone()

            # If table does not exist, create it using the spreadsheet title as the table name
            if not result:
                print(f"Table '{spreadsheet_title}' does not exist. Creating table...")
                create_table_for_sheet(spreadsheet_title, sheet)
                # Sync Google Sheet data to the database
                sync_data_to_db(spreadsheet_title, sheet)

                # After creating table, add the trigger for real-time sync
                create_triggers_for_table(spreadsheet_title)

            else:
                print(f"Table '{spreadsheet_title}' already exists.")

        # Render the template with the Google Sheet link and the update button
        return render(request, 'google_sheet_sync_complete.html', {
            'sheet_id': sheet_id,
            'spreadsheet_title': spreadsheet_title
        })

    return render(request, 'sync_sheet.html')




# Create table with the same name as the Google Sheet
def create_table_for_sheet(sheet_name, sheet):
    columns = sheet.row_values(1)  # Get the first row as column names
    
    # Escape column names with backticks
    column_definitions = ", ".join([f"`{col}` TEXT" for col in columns])

    # Create table with columns matching the Google Sheet
    create_table_query = f"CREATE TABLE `{sheet_name}` ({column_definitions});"
    
    with connection.cursor() as cursor:
        cursor.execute(create_table_query)



# Add this new view to handle the update button

def update_google_sheet(request):
    if request.method == 'POST':
        sheet_id = request.POST.get('sheet_id')
        
        # Open the Google Sheet by ID
        client = authenticate_google_sheets()
        spreadsheet = client.open_by_key(sheet_id)
        spreadsheet_title = spreadsheet.title

        # Get the first worksheet
        sheet_list = spreadsheet.worksheets()
        sheet = sheet_list[0]  # Using the first worksheet

        # Clear existing data and re-sync the data
        with connection.cursor() as cursor:
            cursor.execute(f"TRUNCATE TABLE {spreadsheet_title}")  # Clear all data from the table
            sync_data_to_db(spreadsheet_title, sheet)
            cursor.execute("TRUNCATE TABLE webhook_queue")
        # Return a JSON response to indicate success
        return JsonResponse({'status': 'success'})

    return JsonResponse({'status': 'error'}, status=400)


 
# Sync Google Sheet data to the newly created table
def sync_data_to_db(sheet_name, sheet):
    rows = sheet.get_all_values()[1:]  # Exclude the first row (header)
    columns = sheet.row_values(1)  # Get the first row as column names

    # Escape column names with backticks to handle spaces and special characters
    escaped_columns = [f"`{col}`" for col in columns]

    with connection.cursor() as cursor:
        for row in rows:
            placeholders = ', '.join(['%s'] * len(row))
            query = f"INSERT INTO `{sheet_name}` ({', '.join(escaped_columns)}) VALUES ({placeholders})"
            cursor.execute(query, row)




def get_table_columns(table_name):
    """Fetch column names of the given table."""
    with connection.cursor() as cursor:
        cursor.execute("SHOW COLUMNS FROM %s" % table_name)
        columns = [row[0] for row in cursor.fetchall()]
    return columns

def create_triggers_for_table(table_name):
    columns = get_table_columns(table_name)
    if not columns:
        print(f"No columns found for table '{table_name}'.")
        return

    # Use IFNULL to ensure no NULL values are passed to CONCAT_WS
    new_values = ', '.join([f"IFNULL(NEW.`{col}`, '')" for col in columns])
    old_values = ', '.join([f"IFNULL(OLD.`{col}`, '')" for col in columns])

    # Trigger for INSERT operations
    insert_trigger_query = f"""
    CREATE TRIGGER after_insert_{table_name}_trigger
    AFTER INSERT ON `{table_name}`
    FOR EACH ROW
    BEGIN
        CALL notify_webhook('insert', CONCAT_WS('|', {new_values}), '{table_name}');
    END;
    """

    # Trigger for UPDATE operations
    update_trigger_query = f"""
    CREATE TRIGGER after_update_{table_name}_trigger
    AFTER UPDATE ON `{table_name}`
    FOR EACH ROW
    BEGIN
        CALL notify_webhook('update', CONCAT_WS('|', {new_values}), '{table_name}');
    END;
    """

    # Trigger for DELETE operations
    delete_trigger_query = f"""
    CREATE TRIGGER after_delete_{table_name}_trigger
    AFTER DELETE ON `{table_name}`
    FOR EACH ROW
    BEGIN
        CALL notify_webhook('delete', CONCAT_WS('|', {old_values}), '{table_name}');
    END;
    """

    with connection.cursor() as cursor:
        cursor.execute(insert_trigger_query)
        cursor.execute(update_trigger_query)
        cursor.execute(delete_trigger_query)

      

#this function handle all change happend form database
@csrf_exempt
def webhook_notify_update(request):
    if request.method == 'POST':
        action_type = request.POST.get('action_type')
        row_key = request.POST.get('row_key')
        table_name = request.POST.get('table_name')

        logger.info(f"Received webhook: {action_type}, {row_key}, {table_name}")

        print(f"Webhook received: {action_type}, {row_key}, {table_name}")
        # Authenticate and open the Google Sheet by the table name (same as the sheet name)
        client = authenticate_google_sheets()
        spreadsheet = client.open(table_name)
        sheet = spreadsheet.sheet1  # Assuming the first sheet

        # Split the row_key into individual column values
        row_key_values = row_key.split('|')

        # Perform action based on the webhook event type
        if action_type == 'insert':
            # Insert the new row into Google Sheets
            sheet.append_row(row_key_values)

        elif action_type == 'update':
            # Fetch the row number to update
            rows = sheet.get_all_values()
            for idx, row in enumerate(rows):
                if row[:len(row_key_values)] == row_key_values:  # Match the unique columns
                    # Update the corresponding row in Google Sheets
                    for col_idx, value in enumerate(row_key_values):
                        sheet.update_cell(idx + 1, col_idx + 1, value)  # Update each cell in the row
                    break

        elif action_type == 'delete':
            # Fetch the row number to delete
            rows = sheet.get_all_values()
            for idx, row in enumerate(rows):
                if row[:len(row_key_values)] == row_key_values:  # Match the unique columns
                    sheet.delete_row(idx + 1)  # Delete the corresponding row in Google Sheets
                    break

        return JsonResponse({'status': 'success'})

    return JsonResponse({'status': 'error'}, status=400)


def process_webhook_queue(request):
    """Process the webhook queue and send HTTP POST requests."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT id, action_type, row_key, table_name FROM webhook_queue")
        rows = cursor.fetchall()

        for row in rows:
            id, action_type, row_key, table_name = row

            # Prepare the payload
            payload = {
                'action_type': action_type,
                'row_key': row_key,
                'table_name': table_name
            }

            # Send the POST request to your webhook URL
            response = requests.post('http://localhost:8000/webhook/notify/', data=payload)

            if response.status_code == 200:
                # If successful, remove the processed entry from the queue
                cursor.execute("DELETE FROM webhook_queue WHERE id = %s", [id])

    return JsonResponse({'status': 'success', 'message': 'Successfully processed webhook queue'})

