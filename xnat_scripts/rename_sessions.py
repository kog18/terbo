'''
Created on May 10, 2023

@author: Alex
'''

import os
import csv

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
                                old_name = row["xnat:mrscandata/id "].strip()
                                new_name = f"{row['xnat:mrscandata/id '].strip()}_{row['xnat:mrscandata/type '].strip()}"
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



# Example usage
rename_folders("C:\\Users\\Alex\\tmp\\test")

