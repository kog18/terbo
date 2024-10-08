'''
Created on Jun 7, 2023

Scan TERBO projects on NURUPS for subject group values
@author: Alex
'''
from pyxnat import Interface
import os
import smtplib
import re
from datetime import datetime
from email.message import EmailMessage
from difflib import SequenceMatcher
import configparser
import pathlib

verbose = True

def send_email(body):
    
    config = configparser.ConfigParser()
    db_config_path = pathlib.Path(__file__).parent.absolute() / "config.ini"
    db_file_name = config.read(db_config_path)
    
    # Create the base text message.
    msg = EmailMessage()
    msg['Subject'] = config["qc mail"]["subject"]
    msg['From'] = config["qc mail"]["from"]
    msg['To'] = config["qc mail"]["to"]
    msg['Bcc'] = config["qc mail"]["bcc"]
    msg.set_content(body)
    
    current_datetime = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    str_current_datetime = str(current_datetime)
    file_name = os.path.join(os.path.expanduser('~'), "log", "scan_"+str_current_datetime+".log")
    
    # Make a local copy of what we are going to send.
    with open(file_name, 'wb') as f:
        f.write(bytes(msg))
    
    # Send the message via local SMTP server.
    with smtplib.SMTP('localhost') as s:
        s.send_message(msg)

def create_email(errors_array,count_array):
    email_body="This is an automated message.\n\n"
    email_body+="Project summary:\n\n"
    
    for key in count_array.keys():
        project=key
        email_body+=f"Project: {project}: {count_array[project]} session{'' if count_array[project] == 1 else 's'}\n"
    
    
    email_body+="\n\nThe following errors were found in TERBO projects on NURIPS:"    
    for key in errors_array.keys():
        project=key
        email_body+=f"\n\nProject: {project}\n"
        for s in errors_array[project].keys():
            subject=s
            error=""
            if len(errors_array[project][subject]) > 1:
                for item in errors_array[project][subject]:
                    if len(error)==0:
                        error+=item[0]
                    else:
                        error+=", "+item[0]
            else:
                error+=str(errors_array[project][subject][0][0])    

            email_body+=f"\n\tSubject: {subject}: {error}"
    
    email_body+="\n\nTo modify the items listed above, please go to NURIPS <nuripsweb01.fsm.northwestern.edu>"
    return email_body            

# Checks if a string consists of 6 or 7 numbers, an optional letter at the end and no special characters.
def is_valid_label(id_string):
    special_characters = re.compile(r"[^\d\w]")
    if len(id_string) < 6 or len(id_string) > 8 :
        return False
    if special_characters.search(id_string):
        return False
    if (len(id_string) == 7 or len(id_string) == 8) and id_string[-1].isalpha():
        return True
    if (len(id_string) == 6 or len(id_string) == 7) and id_string.isdigit():
        return True        
    
nurips = Interface(config="./nurips.cfg")

project_list=('TERBO_Baylor','TERBO_Lurie','TERBO_Miami','TERBO_Bronx','TERBO_Colorado','TERBO_StJude','TERBO_UCSD')

#TODO:
# def check_resources():
# pass

audit_array=dict()
count_array=dict()

for p in project_list:  
    sess_count=0      
    project = nurips.select.project(p)
    if verbose:
        print(f'Project: {p}')
        
    subjects = project.subjects().get()

    sub_arr=dict()
    for s in subjects:
        subject_errors=[]
        slabel=project.subject(s).attrs.get("label")
        group=project.subject(s).attrs.get("group")

        if group:
            if not ("YA" in group or "YT" in group):
                ## Malformed group value
                if len(subject_errors)>0:
                    subject_errors.append([f"malformed group: {group}"])
                else:
                    subject_errors=[[f"malformed group: {group}"]]
                
                # Check if subject id is valid
                if not is_valid_label(slabel):

                    if len(subject_errors)>0:
                        subject_errors.append(["malformed subject id"])
                    else:
                        subject_errors=[["malformed subject id"]]
            else:
                # Check validity of subject id if group value is correct
                if not is_valid_label(slabel):

                    if len(subject_errors)>0:
                        subject_errors.append(["malformed subject id"]) 
                    else:
                        subject_errors=[["malformed subject id"]]
        else:
            ## Missing group value

                if len(subject_errors)>0:
                    subject_errors.append(["missing group"]) 
                else:
                    subject_errors=[["missing group"]]
                
                # Check if subject id is valid
                if not is_valid_label(slabel):

                    if len(subject_errors)>0:
                        subject_errors.append(["malformed subject id"]) 
                    else:
                        subject_errors=["malformed subject id"]
        
        if verbose:
            print(f'\tsubject: {slabel}, group: {group}')
        
        for session in project.subject(s).experiments().get():
            sess_count+=1
            #session_errors=[]
            sess_label=project.subject(s).experiment(session).label()
            resources = project.subject(s).experiment(session).resources()
            if verbose:
                print(f'\t\tsession: {sess_label}')
            #print(f"resource len: {len(resources.get())}")
            resource_count=0
            if len(resources.get()) == 0:
                
                if verbose:
                    print("\t\tmissing resource")

                if len(subject_errors)>0 or subject_errors is not None:
                    subject_errors.append([f"missing behavioral data folder in session {sess_label}"])
                else:
                    subject_errors=[f"missing behavioral data folder in session {sess_label}"]
                
            for resource in resources:
                r=resource.label().lower()
                
                # Checking for misspellings on "behavioral"
                match_score=SequenceMatcher(None, r, 'behavioral').ratio()
                if verbose:
                    print(f"Match score: {match_score}")
                    
                if match_score <1 and match_score > .7:
                    if len(subject_errors)>0 or subject_errors is not None:
                        subject_errors.append([f"misspelled behavioral data folder name ('{r}') in session {sess_label}"])
                    else:
                        subject_errors=[f"misspelled behavioral data folder name ('{r}') in session {sess_label}"]
                
                # Checking for incorrect Resources structure. Data folder shouldn't be called "resources".        
                match_score=SequenceMatcher(None, r, 'resources').ratio()        
                if match_score == 1 or match_score > .7:
                    if len(subject_errors)>0 or subject_errors is not None:
                        subject_errors.append([f"'{r}' is not a valid data folder name in session {sess_label}. Bad resources structure."])
                    else:
                        subject_errors=[f"'{r}' is not a valid data folder name in session {sess_label}. Bad resources structure."]
                                
                if verbose:
                    print(f"\t\tresource len: {len(project.subject(s).experiment(session).resources().get())}")
                    print(f'\t\t\tResource type: {resource.label()}, # of files: {len(project.subject(s).experiment(session).resource(resource.id()).files().get())}')
            
        # if verbose:
        #     print(f"\tsubject errors2: {subject_errors}")    

        if len(subject_errors)>0:
            sub_arr[slabel]=subject_errors
    # if len(sub_arr)>0:
    #     print(f"\tSubarr: {sub_arr}")     
    count_array[p]=sess_count
           
    if len(sub_arr)>0:
        audit_array[p]=sub_arr       
     
if verbose:
    #print(f"Audit array2: {audit_array}")
    print(create_email(audit_array, count_array))
    
send_email(create_email(audit_array, count_array))

