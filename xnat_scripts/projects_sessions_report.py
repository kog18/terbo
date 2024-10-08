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
import configparser
import pathlib

# for key, val in sorted(os.environ.items()):
#     print(key)
#     vals = sorted(val.split(os.pathsep))
#     print('    ' + '\n    '.join(vals))

verbose = False

def send_email(body):
    
    config = configparser.ConfigParser()
    db_config_path = pathlib.Path(__file__).parent.absolute() / "config.ini"
    db_file_name = config.read(db_config_path)
    
    # Create the base text message.
    msg = EmailMessage()
    msg['Subject'] = config["qc lei mail"]["subject"]
    msg['From'] = config["qc lei mail"]["from"]
    msg['To'] = config["qc lei mail"]["to"]
    msg['Cc'] = config["qc lei mail"]["cc"]
    msg['Bcc'] = config["qc lei mail"]["bcc"]
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
    
    
    email_body+="\n\nThe following is a summary of the TERBO projects on NURIPS:"    
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

            email_body+=f"\n\tSubject: {subject}: Group: {errors_array[project][subject][0]}"
            errors_array[project][subject].pop(0)
            email_body+=f"\n\t\tSessions: "
            for i in errors_array[project][subject]:
                email_body+=f" {i} "
    
    #email_body+="\n\nTo modify the items listed above, please go to NURIPS <nuripsweb01.fsm.northwestern.edu>"
    return email_body            
   
    
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
        if verbose:
            print(f"Group: {group}")
        if group:
            subject_errors.append(group)
 
        else:
            subject_errors.append("***missing group***")
 
        
        if verbose:
            print(f'\tsubject: {slabel}, group: {group}')
        
        for session in project.subject(s).experiments().get():
            sess_count+=1
            #session_errors=[]
            sess_label=project.subject(s).experiment(session).label()
            subject_errors.append(sess_label)
            
        if verbose:
            print(f"\tsubject errors2: {subject_errors}")    

        if len(subject_errors)>0:
            sub_arr[slabel]=subject_errors
    
    count_array[p]=sess_count
           
    if len(sub_arr)>0:
        audit_array[p]=sub_arr       
     
if verbose:
    #print(f"Audit array2: {audit_array}")
    print(create_email(audit_array, count_array))
    
send_email(create_email(audit_array, count_array))

