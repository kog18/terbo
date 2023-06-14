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
import sys
from requests.auth import HTTPBasicAuth
#from pickle import TRUE 

# Changing the downloaded file structure to combine scan ID with scan type for folder names and create DICOM and BIDS folders
def rename_folders(root_path):
    for folder1 in os.listdir(root_path):
        for folder2 in os.listdir(os.path.join(root_path, folder1)):
            scans_folder = os.path.join(root_path, folder1, folder2, "SCANS")
            if os.path.isdir(scans_folder):
                metadata_folder = os.path.join(root_path, folder1, folder2, "metadata")
                if os.path.isdir(metadata_folder):
                    csv_path = os.path.join(metadata_folder, "scan_metadata.csv")
                    if os.path.isfile(csv_path):
                        with open(csv_path) as csv_file:
                            csv_reader = csv.DictReader(csv_file, skipinitialspace=True)
                            for row in csv_reader:
                                old_name = row["ID"].strip()
                                new_name = f"{row['ID'].strip()}_{row['type'].strip()}"
                                if os.path.isdir(os.path.join(scans_folder, old_name)):
                                    os.rename(os.path.join(scans_folder, old_name), os.path.join(scans_folder, new_name))
                                    print(f"Renamed {os.path.join(scans_folder, old_name)} to {os.path.join(scans_folder, new_name)}")
                                else:
                                    print(f"Could not find directory {os.path.join(scans_folder, old_name)}")
                    else:
                        print(f"Could not find scan_metadata.csv in {metadata_folder}")
                else:
                    print(f"Could not find metadata folder in {os.path.join(root_path, folder1, folder2)}")
            else:
                print(f"Could not find SCANS folder in {os.path.join(root_path, folder1, folder2)}")
    
    # Move YA content to YA/DICOM
    ya_folder = os.path.join(root_path, "YA")
    if os.path.isdir(ya_folder):
        dicom_folder = os.path.join(ya_folder, "DICOM")
        if not os.path.isdir(dicom_folder):
            os.mkdir(dicom_folder)
        for item in os.listdir(ya_folder):
            if item != "DICOM":
                src = os.path.join(ya_folder, item)
                dst = os.path.join(dicom_folder, item)
                os.rename(src, dst)
    
        # Add BIDS folder to YA
        bids_folder = os.path.join(ya_folder, "BIDS")
        if not os.path.isdir(bids_folder):
            os.mkdir(bids_folder)
    
    # Move YT content to YT/DICOM
    yt_folder = os.path.join(root_path, "YT")
    if os.path.isdir(yt_folder):
        dicom_folder = os.path.join(yt_folder, "DICOM")
        if not os.path.isdir(dicom_folder):
            os.mkdir(dicom_folder)
        for item in os.listdir(yt_folder):
            if item != "DICOM":
                src = os.path.join(yt_folder, item)
                dst = os.path.join(dicom_folder, item)
                os.rename(src, dst)
    
        # Add BIDS folder to YT
        bids_folder = os.path.join(yt_folder, "BIDS")
        if not os.path.isdir(bids_folder):
            os.mkdir(bids_folder)

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
        # for record in list_of_rows:
        #     group_id=record[2]
    else:
        print(f"Failed to retrieve subject group. Status code: {response.status_code}")

    return group_id
        
def create_metadata(auth, api_path, output_dir, level, session_label):
    
    print(f'{api_path}')
    # Get session list
    url = api_path
    response = requests.get(url, auth=auth)

    
    if response.status_code == 200:
        decoded_content = response.content.decode('utf-8')
        #csv_reader = csv.reader(decoded_content.splitlines(), delimiter=',')
        print(f"Downloading {level} metadata.")
        # make metadata dir
        meta_dir = os.path.join(output_dir,"metadata")
        os.makedirs(meta_dir, exist_ok=True)
        
        # write out the csv file
        with open(f'{meta_dir}/{level}_metadata.csv', "w", newline='') as csvFile:
            writer = csv.writer(csvFile)
            for line in decoded_content.splitlines():
                writer.writerow(line.split(','))
        # print("Done.")
    else:
        print(f"Failed to retrieve the {level} metadata. Status code: {response.status_code}")
        
    
    
def download_xnat_data(host, username, password, session_labels, overwrite, output_dir, project_id):
    # Authenticate with XNAT using username and password
    auth = HTTPBasicAuth(username, password)

    # Loop through each session label and download its data
    for session_label in session_labels:
        
        xnat_url = f"{host}/data/archive/projects/{project_id}/experiments?xsiType=xnat:mrSessionData&format=csv&columns=ID,label,date,xnat:subjectData/label"
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
                proceed=True
                session_label_xnat = record[4]
                
                if session_label == session_label_xnat:
                    # Extract the session id and date from the session data
                    session_id = record[3]
                    session_date = record[5].replace('-', '')
                    
                    
                    group = get_subject_group(host,auth,session_id)

                    # Determine the output directory based on the session label
                    if group == "YT":
                        output_directory = os.path.join(output_dir, 'YT', f'YT-{session_label}-{session_date}')
                    elif group == "YA":
                        output_directory = os.path.join(output_dir, 'YA', f'YA-{session_label}-{session_date}')
                    else:
                        print(f"Invalid group: {group}. Session: {session_label}")
                        continue
                                        
                    # # Determine the output directory based on the session label
                    # if session_label.startswith('7'):
                    #     output_directory = os.path.join(output_dir, 'YT', f'YT-{session_label}-{session_date}')
                    # elif session_label.startswith('4'):
                    #     output_directory = os.path.join(output_dir, 'YA', f'YA-{session_label}-{session_date}')
                    # else:
                    #     print(f"Invalid session label: {session_label}")
                    #     continue
    
                    # Create the output directory if it doesn't exist
                    try:
                        os.makedirs(output_directory, exist_ok=False)
                    except:
                        print(f'Directory {output_directory} already exists. Assuming data downloaded previously.')
                        proceed=False                     
                            
                    if proceed:
                        
                        print (f"Downloading {session_label} data")
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
                        
                        # Get metadata
                        #session_api_path = f'{host}/data/archive/projects/{project_id}/experiments?xsiType=xnat:mrSessionData&format=csv&columns=ID,label,xnat:subjectData/label'
                        # scan_api_path = f'{host}/data/archive/projects/{project_id}/experiments?xsiType=xnat:mrSessionData&format=csv&columns=project,label,xnat:mrScanData/ID,xnat:mrScanData/type'
                        scan_api_path = f'{host}/data/archive/experiments/{session_id}/scans?format=csv&columns=xnat:mrSessionData/project,xnat:mrSessionData/label,quality,ID,type,note'
                        #create_metadata(auth, session_api_path, output_directory, "session", session_label)         
                        create_metadata(auth, scan_api_path, output_directory, "scan", session_label)
                         
                        print(f"Finished downloading {session_label}.\n")
        else:
            print(f"Failed to retrieve scan data for session {session_label}. Status code: {response.status_code}")


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
    args = parser.parse_args()

    
    # Need a working directory in user's home to store download information 
    home_directory = os.path.expanduser( '~' )
    output_directory = os.path.join( home_directory, 'xnat_download')
    
    
    # Create working directory. This directory will store information about downloaded data.
    if not os.path.isdir(output_directory):
        os.makedirs(output_directory)
    
    # Split the session labels into a list
    session_labels = args.session_labels.split(',')

    # If password argument is not provided, prompt the user for the password
    if not args.password:
        args.password = getpass.getpass(prompt='XNAT password: ')

    # Download the data
    download_xnat_data(args.fqdn, args.username, args.password, session_labels, args.overwrite, args.output_dir, args.project_id)
    rename_folders(args.output_dir)
