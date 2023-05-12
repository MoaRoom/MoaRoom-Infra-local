#!/usr/bin/python3
import requests
from fastapi import FastAPI
import os
import json
import yaml
import res.Dto as Dto
import res.Urls as Urls
import numpy as np

app = FastAPI()


def yaml_to_json(id, isProfessor, lecture_id=-1):
    if isProfessor:
        role = "professor"
    else:
        role = "student"
    f = open("./res/remote-deploy-%s.yml" % role, 'r')
    ID = str(id)

    port_list = list(np.load("./res/port_list.npy"))

    # find available port
    for port_num in range(8887, len(port_list)):
        # no pod assigned
        if port_list[port_num] == False:
            PORT = port_num
            port_list[port_num] = True
            np.save("./res/port_list.npy", port_list)
            break
        else:
            continue

    # apply env var
    file = f.read().replace("{{ ID }}", ID)
    file = file.replace("{ PORT }", str(PORT))
    contents = file.split("---")
    for i in range(len(contents)):
        with open("./res/tmp%d.yml" % i, "w") as tmp:
            tmp.write(contents[i])

    # convert yaml to json
    for i in range(len(contents)):
        with open("./res/tmp%d.yml" % i, 'r') as yaml_in, open("./res/tmp%d.json" % i, "w") as json_out:
            yaml_object = yaml.safe_load(yaml_in)
            json.dump(yaml_object, json_out)

    return len(contents), PORT  # object file num, port


@app.post("/professor/")
async def create_professor_res(professor_info: Dto.UsersModel = None):
    id = professor_info.id

    json_num, PORT = yaml_to_json(id, True)

    for i in range(json_num):
        json_str = json.load(open(
            "./res/tmp%d.json" % i))
        if json_str['kind'] == "Pod":
            url = Urls.kube_base_url+"/api/v1/namespaces/professor-ns/pods"
        elif json_str['kind'] == "Service":
            url = Urls.kube_base_url+"/api/v1/namespaces/professor-ns/services"
        headers = {"Authorization": "Bearer %s" % (os.getenv('TOKEN')),
                   'Accept': 'application/json', "Content-Type": "application/json"}
        result = requests.post(url, data=json.dumps(json_str),
                               headers=headers, verify=os.getenv('CACERT')).text
        if result == False:  # TODO deliver error message
            print("Error in creating professor, id:"+id)
        else:
            print("Professor %d's port is %d" %
                  (id, PORT))


@app.post("/lecture/")
async def create_lecture(lecture_info: Dto.LectureModel = None):
    json_str = requests.get(
        Urls.base_url+"?lecture_id="+lecture_info.lecture_id).text
    data_users_assigned = list(json.loads(json_str))  # json to list[dict]

    student_pod_infos = []
    for user in data_users_assigned:
        id = user.id
        lecture_id = lecture_info.lecture_id
        json_num, PORT = yaml_to_json(id, False, lecture_id)
        for i in range(json_num):
            json_str = json.load(open("./res/tmp%d.json" % i))
            if json_str['kind'] == "Pod":
                url = Urls.kube_base_url+"/api/v1/namespaces/student-ns/pods"
            elif json_str['kind'] == "Service":
                url = Urls.kube_base_url+"/api/v1/namespaces/student-ns/services"
            headers = {"Authorization": "Bearer %s" % (os.getenv('TOKEN')),
                       'Accept': 'application/json', "Content-Type": "application/json"}
            result = requests.post(url, data=json.dumps(json_str),
                                   headers=headers, verify=os.getenv('CACERT')).text
            if result == False:  # TODO deliver error message
                print("Error in creating student, id:"+id)
            else:
                student_pod_infos.append(
                    Dto.URLModel(id, lecture_id, Urls.base_url+":%d" % PORT))
                print("Student %d's port is %d" %
                      (id, PORT))
        print(student_pod_infos)
