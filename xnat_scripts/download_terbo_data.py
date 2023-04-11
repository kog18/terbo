'''
Created on Apr 3, 2023

@author: Alex
'''
import getpass
import os
import argparse
import requests
import csv
import json
import zipfile
import shutil
from requests.auth import HTTPBasicAuth
from pickle import TRUE 

# 

def download_xnat_data(username, password, session_labels, overwrite, output_dir, project_id):
    # Authenticate with XNAT using username and password
    auth = HTTPBasicAuth(username, password)

    # Loop through each session label and download its data
    for session_label in session_labels:
        
        xnat_url = f"https://nurips-dev.fsm.northwestern.edu/data/archive/projects/{project_id}/experiments?xsiType=xnat:mrSessionData&format=csv&columns=ID,label,date,xnat:subjectData/label"
        print(xnat_url)
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
                session_label_xnat = record[4]
                
                if session_label == session_label_xnat:
                    # Extract the session id and date from the session data
                    session_id = record[3]
                    session_date = record[5].replace('-', '')
    
                    # Determine the output directory based on the session label
                    if session_label.endswith('7'):
                        output_directory = os.path.join(output_dir, 'YT', f'YT-{session_label}-{session_date}')
                    elif session_label.endswith('4'):
                        output_directory = os.path.join(output_dir, 'YA', f'YA-{session_label}-{session_date}')
                    else:
                        print(f"Invalid session label: {session_label}")
                        continue
    
                    # Create the output directory if it doesn't exist
                    os.makedirs(output_directory, exist_ok=True)
    
                    # Download the scan data
                    scan_url = f"https://nurips-dev.fsm.northwestern.edu/data/experiments/{session_id}/scans/ALL/files?format=zip&structure=legacy"
                    print(scan_url)
                    response = requests.get(scan_url, auth=auth, stream=True)
    
                    # Save the scan data to a file
                    output_filename = f"{session_label}_{session_date}.zip"
                    output_path = os.path.join(output_directory, output_filename)
                    with open(output_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=1024):
                            f.write(chunk)
                    
                    print ("Download completed. Extracting...")
                    
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
                          
                    try:
                        shutil.rmtree(os.path.join(output_directory,session_label))
                    except FileNotFoundError: 
                        print (f"File Not Found: {os.path.join(output_directory,session_label)}") 
                    except : 
                        print (f"Error deleting {os.path.join(output_directory,session_label)}")   
                              
                    print("Done.")
        else:
            print(f"Failed to retrieve scan data for session {session_label}. Status code: {response.status_code}")


if __name__ == '__main__':
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Download imaging data from a remote XNAT system')
    parser.add_argument('-u', '--username', required=True, help='XNAT username')
    parser.add_argument('-p', '--password', help='XNAT password')
    parser.add_argument('-s', '--session-labels', required=True, help='XNAT session label(s) (comma-separated)')
    parser.add_argument('-x', '--overwrite', action='store_true', help='Overwrite output directory if it exists')
    parser.add_argument('-d', '--output-dir', required=True, help='Output directory for downloaded data')
    parser.add_argument('-i', '--project-id', required=True, help='XNAT project ID')
    args = parser.parse_args()

    # Split the session labels into a list
    session_labels = args.session_labels.split(',')

    # If password argument is not provided, prompt the user for the password
    if not args.password:
        args.password = getpass.getpass(prompt='XNAT password: ')

    # Download the data
    download_xnat_data(args.username, args.password, session_labels, args.overwrite, args.output_dir, args.project_id)

