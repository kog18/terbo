'''
Created on Jun 7, 2023

Scan TERBO projects on NURUPS for subject group values
@author: Alex
'''
from pyxnat import Interface


nurips = Interface(
               server='https://nuripsweb01.fsm.northwestern.edu',
               user='',
               password='')

project_list=('TERBO_Baylor','TERBO_Lurie','TERBO_Maiami','TERBO_Bronx','TERBO_Colorado','TERBO_StJude','TERBO_UCSD')

for p in project_list:
    project = nurips.select.project(p)
    print(f'Project: {p}')
    subjects = project.subjects().get()
    #print(subjects)
    for s in subjects:
        slabel=project.subject(s).attrs.get("label")
        group=project.subject(s).attrs.get("group")
        print(f'\t\tsubject: {slabel}, group: {group}')



