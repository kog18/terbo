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

verbose = False

def send_email(body):
    # Create the base text message.
    msg = EmailMessage()
    msg['Subject'] = "TERBO QC report"
    msg['From'] = 'TERBO QC <alexandr.kogan@osumc.edu>'
    msg['To'] = 'TERBO Imaging <terbo.imaging.ra@fstrf.org>'
    msg['Bcc'] = 'Alex Kogan <kogan.34@osu.edu>'
    msg.set_content(body)
    
    current_datetime = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
    str_current_datetime = str(current_datetime)
    file_name = os.path.join(os.path.expanduser('~'), "log", "log_"+str_current_datetime+".txt")
    
    # Make a local copy of what we are going to send.
    with open(file_name, 'wb') as f:
        f.write(bytes(msg))
    
    # Send the message via local SMTP server.
    with smtplib.SMTP('localhost') as s:
        s.send_message(msg)

def create_email(errors_array):
    email_body="This is an automated message.\n\n"
    email_body+="The following errors were found in TERBO projects on NURIPS:\n"
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
                error+=errors_array[project][subject][0]    

            email_body+=f"\n\tSubject: {subject}: {error}"
    
    email_body+="\n\nTo modify the items listed above, please go to NURIPS <nuripsweb01.fsm.northwestern.edu>"
    return email_body            

# Checks if a string consists of 6 numbers, an optional letter at the end and no special characters.
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

project_list=('TERBO_Baylor','TERBO_Lurie','TERBO_Maiami','TERBO_Bronx','TERBO_Colorado','TERBO_StJude','TERBO_UCSD')

#TODO:
# def check_resources():
# pass

audit_array=dict()

for p in project_list:        
    project = nurips.select.project(p)
    if verbose:
        print(f'Project: {p}')
        
    subjects = project.subjects().get()

    sub_arr=dict()
    for s in subjects:
        slabel=project.subject(s).attrs.get("label")
        group=project.subject(s).attrs.get("group")

        if group:
            if not (group == "YA" or group == "YT"):
                ## Malformed group value
                sub_arr[slabel]=[f"malformed group: {group}"]
                
                # Check if subject id is valid
                if not is_valid_label(slabel):
                    sub_arr[slabel]=[sub_arr[slabel],["malformed subject id"]] if slabel in sub_arr else ["malformed subject id"]
                audit_array[p]=sub_arr
            else:
                # Check validity of subject id if group value is correct
                if not is_valid_label(slabel):
                    sub_arr[slabel]=[sub_arr[slabel],["malformed subject id"]] if slabel in sub_arr else ["malformed subject id"]
                if len(sub_arr)>0:
                    audit_array[p]=sub_arr                    
        else:
            ## Missing group value
                sub_arr[slabel]=["missing group"]
                
                # Check if subject id is valid
                if not is_valid_label(slabel):
                    sub_arr[slabel]=[sub_arr[slabel],["malformed subject id"]] if slabel in sub_arr else ["malformed subject id"]
                audit_array[p]=sub_arr
            
        if verbose:
            print(f'\tsubject: {slabel}, group: {group}')
        for session in project.subject(s).experiments().get():
            sess_label=project.subject(s).experiment(session).label()
            resources = project.subject(s).experiment(session).resources()
            #print(f'\t\tsession: {sess_label}')
            for resource in resources:
                r=resource.label()
                if verbose:
                    print(f'\t\tsession: {sess_label}')
                    print(f'\t\t\tResource type: {resource.label()}, # of files: {len(project.subject(s).experiment(session).resource(resource.id()).files().get())}')
                #print(f'\t\tresources: {resource.label()}, # of files: {resource.attributes()}')

if verbose:
    print(audit_array)

if verbose:
    print(create_email(audit_array))
    
send_email(create_email(audit_array))

