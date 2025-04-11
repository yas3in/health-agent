import requests

from apps.report.models import Question, Report

LIMESURVEY_PASSWORD = "Voice@Admin"
LIMESURVEY_USERNAME = "Voice@Admin"
LIMESURVEY_URL = "http://144.91.94.174:8080/index.php/admin/remotecontrol"

def release_session_key(session_key):
    payload = {"method": "release_session_key", "params": [session_key], "id": 1}
    response = requests.post(LIMESURVEY_URL, json=payload)
    return response.status_code == 200


def get_list_surveys(session_key):
    payload = {"method": "list_surveys", "params": [session_key, LIMESURVEY_USERNAME], "id": 1}
    response = requests.post(LIMESURVEY_URL, json=payload)
    if response.status_code == 200:
        return response.json().get("result", [])
    raise Exception(f"خطا در دریافت لیست پرسشنامه‌ها: {response.text}")


def list_questions(session_key, survey_id):
    payload = {
        "method": "list_questions",
        "params": [session_key, survey_id],
        "id": 1
    }
    response = requests.post(LIMESURVEY_URL, json=payload)
    if response.status_code == 200:
        return response.json().get("result", [])
    raise Exception(f"خطا در دریافت لیست سوالات: {response.text}")


def save_report(name, sid, description=""):
    try:
        Report.objects.get(sid=sid)
    except:
        instance = Report.objects.create(
            name=name, sid=sid, description=description
        )
        instance.save()
        return instance
    else:
        return None


def save_question(report, question):
    instance = Question.objects.create(
        report=report, question=question
    )
    instance.save()
    return instance
    

def get_session_key():
    payload = {"method": "get_session_key", "params": ["Voice@Admin", "Voice@Admin"], "id": 1}  
    response = requests.post("http://144.91.94.174:8080/index.php/admin/remotecontrol", json=payload)
    if response.status_code == 200:
        return response.json().get("result")
    raise Exception(response.text)


def main():
    survey_dict = {}
    session_key = get_session_key()
    if session_key is not None:
        survey_list = get_list_surveys(session_key)
        for i in survey_list:
            survey_dict.update(i)
            report_instance = save_report(
                name=i["surveyls_title"], sid=i["sid"]
                )
            if report_instance is not None:
                questions = list_questions(session_key, survey_dict["sid"])
                for i in questions:
                    save_question(
                        report=report_instance, question=i["question"]
                        )
    else:
        raise Exception("error in session key")
    return release_session_key(session_key)