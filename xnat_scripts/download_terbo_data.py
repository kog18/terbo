'''
Created on Apr 3, 2023

@author: Alex
'''
import getpass
import os
import argparse
import requests
import csv
import zipfile
import shutil
import sys
from requests.auth import HTTPBasicAuth
import configparser
import psycopg2 
from datetime import datetime
import logging
import pathlib
import smtplib
from email.message import EmailMessage

current_datetime = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
str_current_datetime = str(current_datetime)
file_name = os.path.join(os.path.expanduser('~'), "log", "dw_"+str_current_datetime+".log")

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setLevel(logging.DEBUG)
file_handler = logging.FileHandler(filename=file_name)
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
stdout_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)
logger.addHandler(stdout_handler)
logger.addHandler(file_handler)
logging.getLogger("urllib3").setLevel(logging.WARNING)   
    
logger.debug("Starting...")

""" 
Command line example:

python download_terbo_data.py -f https://nuripsweb01.fsm.northwestern.edu -u ako275 -i TERBO_Lurie -s 400817K,401215D,7056167F,7060217L -d /disk/fsmres_users/ako275/PBS/NIACAL/home/ako275/terbo
 To do: check db connection, insert & select queries
 
"""

dw_projects = dict()
dw_resources = []

def send_email(body):
    

    config = configparser.ConfigParser()
    db_config_path = pathlib.Path(__file__).parent.absolute() / "config.ini"
    db_file_name = config.read(db_config_path)
        
    # Create the base text message.
    msg = EmailMessage()
    msg['Subject'] = config["mail"]["subject"]
    msg['From'] = config["mail"]["from"]
    msg['To'] = config["mail"]["to"]
    msg['Bcc'] = config["mail"]["bcc"]
    msg.set_content(body)
    
    current_datetime = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    str_current_datetime = str(current_datetime)
    file_name = os.path.join(os.path.expanduser('~'), "log", "dw_email_"+str_current_datetime+".log")
    
    # Make a local copy of what we are going to send.
    with open(file_name, 'wb') as f:
        f.write(bytes(msg))
    
    # Send the message via local SMTP server.
    with smtplib.SMTP('localhost') as s:
        s.send_message(msg)

def create_email(dw_projects,dw_resources):
    email_body="This is an automated message.\n\n"
    
    if len(dw_projects)>0:
        email_body+="The following data were downloaded from TERBO projects on NURIPS:\n"
        
        for project in dw_projects.keys():
            email_body+=f"\n\tProject: {project}"
            for s in dw_projects[project]:
                email_body+=f"\n\t\tSession: {s} "
    
    if len(dw_resources)>0:
        email_body+="\n\nResources for the following sessions were downloaded from TERBO projects on NURIPS:\n"
                  
        for s in dw_resources:
            email_body+=f"\n\t\tSession: {s} "
               
    return email_body  
    
def get_db_connection():
    
    #print(f"working dir: {os.getcwd()}")
    # Read the configuration file
    config = configparser.ConfigParser()
    db_config_path = pathlib.Path(__file__).parent.absolute() / "config.ini"
    db_file_name = config.read(db_config_path)
    
    # Get the connection information from the configuration file
    host = config["postgresql"]["host"]
    port = config["postgresql"]["port"]
    database = config["postgresql"]["database"]
    username = config["postgresql"]["username"]
    password = config["postgresql"]["password"]
    
    # Create a connection to the PostgreSQL database
    connection = psycopg2.connect(host=host, port=port, database=database, user=username, password=password)
    
    return connection

def run_query(connection, query):
    """Runs a query and returns the results.

    Args:
        connection (psycopg2.Connection): A connection to the PostgreSQL database.
        query (str): The SQL query to run.

    Returns:
        list: The results of the query.
    """

    # Create a cursor.
    cursor = connection.cursor()

    # Execute the query.
    cursor.execute(query)
    connection.commit()
    
    # Fetch the results.
    if cursor.pgresult_ptr is not None:
        results = cursor.fetchall()
    else:
        results = 'No results returned'    

    # Getting rid of tuples in the query result
    final_result = [i[0] for i in results]
    # Close the cursor.
    cursor.close()

    return final_result

def get_all_resource_types(connection):
    result = run_query(connection, "SELECT type FROM resource_types;") 
    return result

def add_new_resource_type(connection, resource_type):
    result = run_query(connection, f"INSERT INTO resource_types(type) VALUES ('{resource_type}');")
    return result

def get_resource_count_by_type(connection, session_id, resource_type):
    result = run_query(connection, f"SELECT count(*) FROM resources WHERE study_id = '{session_id}' and type_code = (SELECT id FROM resource_types WHERE type = '{resource_type}');")
    return result

def insert_new_resource(connection, session_id, resource_type):
    result = run_query(connection, f"INSERT INTO resources(study_id, first_dw_date, last_dw_date, type_code) VALUES ('{session_id}',NOW(),NOW(),(SELECT id FROM resource_types WHERE type = '{resource_type}'));")
    return result

def update_resource_dw_date(connection, session_id):
    result = run_query(connection, f"UPDATE resources SET last_dw_date = NOW() WHERE study_id = '{session_id}';")
    return result

def update_study_dw_date(connection, session_id):
    result = run_query(connection, f"UPDATE studies SET last_dw_date = NOW() WHERE study_xnat_id = '{session_id}';")
    return result

def insert_new_study(connection, session_label, session_id, project_id):
    result = run_query(connection, f"INSERT INTO studies(study_label, study_xnat_id, study_xnat_project_id, create_date, first_dw_date, last_dw_date) VALUES ('{session_label}','{session_id}','{project_id}',NOW(),NOW(),NOW());")
    return result

def get_all_studies(connection):
    result = run_query(connection, "SELECT * FROM studies;")
    return result

def is_study(connection, session_id):
    result = run_query(connection, f"SELECT count(*) FROM studies where study_xnat_id = '{session_id}';")
    if result[0] != 0:
        return True
    else:
        return False

# # Changing the downloaded file structure to combine scan ID with scan type for folder names and create DICOM and BIDS folders
# def rename_folders(root_path):
#     for folder1 in os.listdir(root_path):
#         for folder2 in os.listdir(os.path.join(root_path, folder1)):
#             if folder2 == 'DICOM':
#                 dicom_folder = os.path.join(root_path, folder1, folder2)
#                 for folder_session in os.listdir(dicom_folder):
#                     scans_folder = os.path.join(root_path, folder1, folder2, folder_session, "SCANS")
#                     if os.path.isdir(scans_folder):
#                         metadata_folder = os.path.join(root_path, folder1, folder2, folder_session, "metadata")
#                         if os.path.isdir(metadata_folder):
#                             csv_path = os.path.join(metadata_folder, "scan_metadata.csv")
#                             if os.path.isfile(csv_path):
#                                 with open(csv_path) as csv_file:
#                                     csv_reader = csv.DictReader(csv_file, skipinitialspace=True)
#                                     for row in csv_reader:
#                                         old_name = row["ID"].strip()
#                                         new_name = row['ID'].strip()+'_'+row['type'].strip().replace('/','_').replace(' ','_').replace('\\','_')
#                                         if os.path.isdir(os.path.join(scans_folder, old_name)):
#                                             os.rename(os.path.join(scans_folder, old_name), os.path.join(scans_folder, new_name))
#                                             print(f"Renamed {os.path.join(scans_folder, old_name)} to {os.path.join(scans_folder, new_name)}")
#                                             logger.debug(f"Renamed {os.path.join(scans_folder, old_name)} to {os.path.join(scans_folder, new_name)}")
#                                         else:
#                                             print(f"Could not find directory {os.path.join(scans_folder, old_name)}. Assuming already renamed.")
#                                             logger.debug(f"Could not find directory {os.path.join(scans_folder, old_name)}. Assuming already renamed.")
#                             else:
#                                 print(f"Could not find scan_metadata.csv in {metadata_folder}")
#                                 logger.debug(f"Could not find scan_metadata.csv in {metadata_folder}")
#                         else:
#                             print(f"Could not find metadata folder in {os.path.join(root_path, folder1, folder_session)}")
#                             logger.debug(f"Could not find metadata folder in {os.path.join(root_path, folder1, folder_session)}")
#                     else:
#                         print(f"Could not find SCANS folder in {os.path.join(root_path, folder1, folder_session)}")
#                         logger.debug(f"Could not find SCANS folder in {os.path.join(root_path, folder1, folder_session)}")
        
# Changing the downloaded file structure to combine scan ID with scan type for folder names and create DICOM and BIDS folders
def rename_folders(root_path):

    scans_folder = os.path.join(root_path, "SCANS")
    if os.path.isdir(scans_folder):
        metadata_folder = os.path.join(root_path, "metadata")
        if os.path.isdir(metadata_folder):
            csv_path = os.path.join(metadata_folder, "scan_metadata.csv")
            if os.path.isfile(csv_path):
                with open(csv_path) as csv_file:
                    csv_reader = csv.DictReader(csv_file, skipinitialspace=True)
                    for row in csv_reader:
                        old_name = row["ID"].strip()
                        new_name = row['ID'].strip()+'_'+row['type'].strip().replace('/','_').replace(' ','_').replace('\\','_')
                        if os.path.isdir(os.path.join(scans_folder, old_name)):
                            os.rename(os.path.join(scans_folder, old_name), os.path.join(scans_folder, new_name))
                            print(f"Renamed {os.path.join(scans_folder, old_name)} to {os.path.join(scans_folder, new_name)}")
                            logger.debug(f"Renamed {os.path.join(scans_folder, old_name)} to {os.path.join(scans_folder, new_name)}")
                        else:
                            print(f"Could not find directory {os.path.join(scans_folder, old_name)}. Assuming already renamed.")
                            logger.debug(f"Could not find directory {os.path.join(scans_folder, old_name)}. Assuming already renamed.")
            else:
                print(f"Could not find scan_metadata.csv in {metadata_folder}")
                logger.debug(f"Could not find scan_metadata.csv in {metadata_folder}")
        else:
            print(f"Could not find metadata folder in {os.path.join(root_path, 'metadata')}")
            logger.debug(f"Could not find metadata folder in {os.path.join(root_path, 'metadata')}")
    else:
        print(f"Could not find SCANS folder in {os.path.join(root_path, 'SCANS')}")
        logger.debug(f"Could not find SCANS folder in {os.path.join(root_path, 'SCANS')}")
                        
def get_subject_group(host, auth, session_id):
    
    get_group_path=f"{host}/data/archive/experiments?format=csv&xnat:mrSessionData/ID={session_id}&columns=xnat:subjectData/group"
    response = requests.get(get_group_path, auth=auth)
    if response.status_code == 200:
        decoded_content = response.content.decode('utf-8')
        csv_reader = csv.reader(decoded_content.splitlines(), delimiter=',')
        list_of_rows = list(csv_reader)
        list_of_rows.pop(0)

        if list_of_rows[0][2]:
            group_id=list_of_rows[0][2]
        else:
            print('The group is not set.')
            logger.debug('The group is not set.')
            group_id=""
        # for record in list_of_rows:
        #     group_id=record[2]
    else:
        print(f"Failed to retrieve subject group. Status code: {response.status_code}")
        logger.debug(f"Failed to retrieve subject group. Status code: {response.status_code}")

    return group_id

def find_seventh_comma_index(text):

    # Strip leading/trailing commas and split by commas
    text_list = text.strip(",").split(",")

    # Check if there are at least 7 commas
    if len(text_list) >= 7:
        # Return the index of the 7th element (6th index due to 0-based indexing)
        return text.find(text_list[7])  # Use comma-separated list element to find it in original string
    else:
        # Return -1 if there are not enough commas
        return -1
    
def extract_session_note(text):

    try:
        # Find the index of the 7th comma
        seventh_comma_index = find_seventh_comma_index(text)
    
        # Extract the relevant portion of the string
        if seventh_comma_index != -1:
            relevant_portion = text[seventh_comma_index:]  # Include text after the 7th comma
    
            # Find the first comma followed by forward slash
            slash_index = relevant_portion.find(",/")
    
            if slash_index != -1:
                # Extract the text before the comma/slash
                return relevant_portion[:slash_index].strip(",")  # Remove leading/trailing commas
            else:
                # Handle case where forward slash is not found
                return relevant_portion.strip(",")  # Remove leading/trailing commas
        else:
            return ""  # Not enough commas
    
    except ValueError:
        # Handle potential errors during string processing
        print("Error: Invalid string format.")
        return ""

                       
def create_metadata(auth, host, output_dir, level, session_id):
    
    api_path = f'{host}/data/archive/experiments/{session_id}/scans?format=csv&columns=xnat:mrSessionData/project,xnat:mrSessionData/label,quality,ID,type,note,xnat:mrSessionData/note'
    print(f'{api_path}')
    # Get session list
    url = api_path
    response = requests.get(url, auth=auth)

    
    if response.status_code == 200:
        decoded_content = response.content.decode('utf-8')
        #csv_reader = csv.reader(decoded_content.splitlines(), delimiter=',')
        logger.debug(f"Downloading {level} metadata.")
        print(f"Downloading {level} metadata.")
        # make metadata dir
        meta_dir = os.path.join(output_dir,"metadata")
        os.makedirs(meta_dir, exist_ok=True)
        
        neworder=[0,2,3,5,6,8,1,4]
        # write out the csv file, change order according to the new order index
        with open(f'{meta_dir}/{level}_metadata.csv', "w", newline='') as csvFile:
            writer = csv.writer(csvFile)
            for line in decoded_content.splitlines():
                line=line.split(',')
                line = [line[i] for i in neworder]
                writer.writerow(line)
        
        # Check if there is a session-level note. If yes, save it in a session metadata file
        #sess_record = decoded_content.splitlines()[1].split('"')
        sess_record = extract_session_note(decoded_content.splitlines()[1])
        print(f'Session level note: {sess_record}')
        if len(sess_record) > 1:
            with open(f'{meta_dir}/session_metadata.txt', "w", newline='') as txtFile:
                txtFile.write(sess_record)        
    else:
        print(f"Failed to retrieve the {level} metadata. Status code: {response.status_code}")
        logger.debug(f"Failed to retrieve the {level} metadata. Status code: {response.status_code}")
        
    
def download_resources(host, auth, session_id, output_dir, session_label):
    resources_path=f"{host}/data/archive/experiments/{session_id}/resources?format=csv&columns=label"
    response = requests.get(resources_path, auth=auth)
    if response.status_code == 200:
        decoded_content = response.content.decode('utf-8')
        csv_reader = csv.reader(decoded_content.splitlines(), delimiter=',')
        list_of_rows = list(csv_reader)
        
        # Remove the header
        list_of_rows.pop(0)
        print(list_of_rows)
        if len(list_of_rows) == 0:
            print('Associated resources not found.')
            logger.debug('Associated resources not found.')

        
        resource_dir = os.path.join(output_dir,"resources")

        # If resource directory exists - remove it
        if os.path.exists(resource_dir) and os.path.isdir(resource_dir):
            shutil.rmtree(resource_dir)
        
        os.makedirs(resource_dir, exist_ok=True)
            
        for row in list_of_rows:
            # If resource exists and files exist for that resource
            if row[1] and row[6]:
                resource_type=row[1]
                resource_url = f"{host}/data/archive/experiments/{session_id}/resources/{resource_type}/files?format=zip&structure=legacy"
                #print(scan_url)
                response = requests.get(resource_url, auth=auth, stream=True)
                    
                resource_type_dir = os.path.join(resource_dir, resource_type)
                
                #TODO: Overwrite logic
                os.makedirs(resource_type_dir, exist_ok=True)
                print(f'Created directory {resource_type_dir}')
                logger.debug(f'Created directory {resource_type_dir}')
                    
                # Save the resource data to a file
                output_filename = f"{session_id}_{resource_type}.zip"
                output_path = os.path.join(resource_type_dir, output_filename)
                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=1024):
                        f.write(chunk)
                
                print (f"Resource {resource_type} download completed. Extracting...")
                logger.debug(f"Resource {resource_type} download completed. Extracting...")
                
                # Extract data without the directory structure (files only), remove the zip file
                with zipfile.ZipFile(output_path) as file:
                    for zip_info in file.infolist():
                        zip_info.filename = zip_info.filename.split("/")[-1]
                        file.extract(zip_info, resource_type_dir)
                
                # Remove the zip file
                os.remove(output_path)       
                
                connection = get_db_connection()
                
                # Check if resource of this type is defined in the db, if not - create it
                all_types = get_all_resource_types(connection)
                print(f"Select result: {all_types}")
                #logger.debug(f"All types: {all_types}, Resource type: {resource_type}")
                
                if resource_type.lower().strip() not in all_types:
                    add_new_resource_type(connection, resource_type.lower().strip())
                                        
                ## Check if the resource of this type for this session was already downloaded and insert resource info into the db, using the type_code, if needed
                res_count = get_resource_count_by_type(connection, session_id, resource_type.lower())
                if int(res_count[0]) > 0:
                    result = update_resource_dw_date(connection, session_id)
                else:    
                    result = insert_new_resource(connection, session_id, resource_type.lower())                
                    print(f"Insert result: {result}")                         
                
                dw_resources.append(session_label+' - '+resource_type)
        # else:
        #     print('Associated resources not found.')
        #     logger.debug('Associated resources not found.')
                
    else:
        print(f"Failed to get resource info. Status code: {response.status_code}")
    
def download_xnat_data(host, username, password, session_labels, overwrite, output_dir, project_id, res_overwrite):
    # Authenticate with XNAT using username and password
    auth = HTTPBasicAuth(username, password)
    
    dw_sessions=[]
    # Loop through each session label and download its data
    for session_label in session_labels:
        
        xnat_url = f"{host}/data/archive/projects/{project_id}/experiments?xsiType=xnat:mrSessionData&format=csv&columns=ID,label,date,xnat:subjectData/label"
        #print(xnat_url)
        # Make a GET request to retrieve the scan data for the session
        response = requests.get(xnat_url, auth=auth)
        
        # Check if the request was successful
        if response.status_code == 200:

            decoded_content = response.content.decode('utf-8')
            csv_reader = csv.reader(decoded_content.splitlines(), delimiter=',')
            list_of_rows = list(csv_reader)
            #json_data = json.dumps(list_of_rows) 
            list_of_rows.pop(0)
                                   
            # Loop through each list of sessions
            for record in list_of_rows:
                proceed=True
                session_label_xnat = record[4]
                
                if session_label == session_label_xnat:
                    # Extract the session id and date from the session data
                    session_id = record[3]
                    session_date = record[5].replace('-', '')                 
                    group = get_subject_group(host,auth,session_id)

                    # Determine the output directory based on the session label
                    if group == "YT":
                        output_directory = os.path.join(output_dir, 'YT', 'DICOM', f'YT-{session_label}-{session_date}') 
                    elif group == "YA":
                        output_directory = os.path.join(output_dir, 'YA', 'DICOM', f'YA-{session_label}-{session_date}')   
                    else:
                        print(f"Invalid group: {group}. Session: {session_label}")
                        logger.debug(f"Invalid group: {group}. Session: {session_label}")
                        continue
                     
                    
                    # The logic is as follows: if the session output directory exists - check if the resource folder exists. If not - download resources. 
                    if os.path.exists(output_directory):
                        if os.path.exists(os.path.join(output_directory,"resources")):
                            if res_overwrite:
                                print(f'Directory {output_directory} already exists. Assuming data downloaded previously. Overwriting resources.')
                                logger.debug(f'Directory {output_directory} already exists. Assuming data downloaded previously. Overwriting resources.')
                                download_resources(host, auth, session_id, output_directory, session_label)
                            else:    
                                print(f'Directory {output_directory} already exists. Assuming data downloaded previously.')
                                logger.debug(f'Directory {output_directory} already exists. Assuming data downloaded previously.')
                        else:
                            print(f'Directory {output_directory} already exists. Downloading resources only.')
                            logger.debug(f'Directory {output_directory} already exists. Downloading resources only.')
                            download_resources(host, auth, session_id, output_directory, session_label)
                            
                        proceed=False
                    else:
                        os.makedirs(output_directory)                    
             
                                                        
                    # Add BIDS folder to YA/YT folder, if doesn't exist
                    if not os.path.exists(os.path.join(output_dir, group, 'BIDS')):
                        os.mkdir(os.path.join(output_dir, group, 'BIDS')) 

                            
                    if proceed:
                        
                        print (f"Downloading {session_label} data")
                        logger.debug(f"Downloading {session_label} data")
                        
                        # Download the scan data
                        scan_url = f"{host}/data/experiments/{session_id}/scans/ALL/files?format=zip&structure=legacy"
                        #print(scan_url)
                        response = requests.get(scan_url, auth=auth, stream=True)
        
                        # Save the scan data to a file
                        output_filename = f"{session_label}_{session_date}.zip"
                        output_path = os.path.join(output_directory, output_filename)
                        with open(output_path, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=1024):
                                f.write(chunk)
                        
                        print ("Download completed. Extracting...")
                        logger.debug("Download completed. Extracting...")
                        
                        # Extract data, remove zip file
                        with zipfile.ZipFile(output_path) as file:
                            for d in file.namelist():
                                if d.startswith(f"{session_label}/SCANS/"):
                                    file.extract(d, output_directory)
                        os.remove(output_path)
                        
                        # Get rid of session_label-named directory
                        try:
                            shutil.move(os.path.join(output_directory,session_label,"SCANS"),output_directory) 
                        except:
                            print(f"Error moving {os.path.join(output_directory,session_label,'SCANS')} to {output_directory}")
                            logger.debug(f"Error moving {os.path.join(output_directory,session_label,'SCANS')} to {output_directory}")  
                               
                        try:
                            shutil.rmtree(os.path.join(output_directory,session_label))
                        except FileNotFoundError: 
                            print (f"File Not Found: {os.path.join(output_directory,session_label)}") 
                            logger.debug(f"File Not Found: {os.path.join(output_directory,session_label)}")
                        except : 
                            print (f"Error deleting {os.path.join(output_directory,session_label)}")   
                            logger.debug(f"Error deleting {os.path.join(output_directory,session_label)}")
                        
                        # Get metadata
                        #session_api_path = f'{host}/data/archive/projects/{project_id}/experiments?xsiType=xnat:mrSessionData&format=csv&columns=ID,label,xnat:subjectData/label'
                        # scan_api_path = f'{host}/data/archive/projects/{project_id}/experiments?xsiType=xnat:mrSessionData&format=csv&columns=project,label,xnat:mrScanData/ID,xnat:mrScanData/type'
                        ##scan_api_path = f'{host}/data/archive/experiments/{session_id}/scans?format=csv&columns=xnat:mrSessionData/project,xnat:mrSessionData/label,quality,ID,type,note'
                        #create_metadata(auth, session_api_path, output_directory, "session", session_label)  
                               
                        create_metadata(auth, host, output_directory, "scan", session_id)
                        download_resources(host, auth, session_id, output_directory, session_label)
                        
                        rename_folders(output_directory)
                        
                        connection = get_db_connection()
                        if is_study(connection, session_id):
                            result = update_study_dw_date(connection, session_id)
                        else:
                            result = insert_new_study(connection, session_label, session_id, project_id)
                            
                        print(f"Insert study result: {result}")
                        
                        result = get_all_studies(connection) 
                        print(f"Select studies result: {result}")
                        
                        dw_sessions.append(session_label)
                        print(f"Finished downloading {session_label}.\n")
                        logger.debug(f"Finished downloading {session_label}.\n")
                        
            if len(dw_sessions)>0:
                dw_projects[project_id]=dw_sessions            
            # rename_folders(output_dir)
        else:
            print(f"Failed to retrieve scan data for session {session_label}. Status code: {response.status_code}")
            logger.debug(f"Failed to retrieve scan data for session {session_label}. Status code: {response.status_code}")

    #rename_folders(output_dir)    
        
if __name__ == '__main__':
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Download imaging data from a remote XNAT system')
    parser.add_argument('-f', '--fqdn', required=True, help='XNAT URL')
    parser.add_argument('-u', '--username', required=True, help='XNAT username')
    parser.add_argument('-p', '--password', help='XNAT password')
    parser.add_argument('-s', '--session-labels', required=True, help='XNAT session label(s) (comma-separated)')
    parser.add_argument('-x', '--overwrite', action='store_true', help='Overwrite output directory if it exists')
    parser.add_argument('-d', '--output-dir', required=True, help='Output directory for downloaded data')
    parser.add_argument('-i', '--project-id', required=True, help='XNAT project ID')
    parser.add_argument('-r', '--res_overwrite', action='store_true', help='Overwrite resource if session directory exists')
    args = parser.parse_args()

    
    # Split the session labels into a list
    session_labels = args.session_labels.split(',')

    # If password argument is not provided, prompt the user for the password
    if not args.password:
        args.password = getpass.getpass(prompt='XNAT password: ')

    # Download the data
    download_xnat_data(args.fqdn, args.username, args.password, session_labels, args.overwrite, args.output_dir, args.project_id, args.res_overwrite)
    
    if len(dw_projects)>0 or len(dw_resources)>0:
        print(create_email(dw_projects,dw_resources))
        logger.debug(create_email(dw_projects,dw_resources))
        send_email(create_email(dw_projects,dw_resources))
   
