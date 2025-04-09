import requests
from dotenv import load_dotenv
import os
import json

from apps.report.models import Question, Report

load_dotenv()

LIMESURVEY_URL = os.getenv("LIMESURVEY_URL")
LIMESURVEY_USERNAME = os.getenv("LIMESURVEY_USERNAME")
LIMESURVEY_PASSWORD = os.getenv("LIMESURVEY_PASSWORD")



class LimeSurvay:

    def __init__(self):
        self.username = LIMESURVEY_USERNAME
        self.password = LIMESURVEY_PASSWORD
        self.url = LIMESURVEY_URL

    def get_session_key(self):
        payload = {"method": "get_session_key", "params": [self.username, self.password], "id": 1}
        response = requests.post(self.url, json=payload)
        if response.status_code == 200:
            return response.json().get("result")
        return None

    def release_session_key(self, session_key):
        payload = {"method": "release_session_key", "params": [session_key], "id": 1}
        response = requests.post(self.url, json=payload)
        return response.status_code == 200
    
    def get_list_surveys(self, session_key):
        payload = {"method": "list_surveys", "params": [session_key, self.username], "id": 1}
        response = requests.post(self.url, json=payload)
        if response.status_code == 200:
            return response.json().get("result", [])
        raise Exception(f"خطا در دریافت لیست پرسشنامه‌ها: {response.text}")

    def list_questions(self, session_key, survey_id):
        payload = {
            "method": "list_questions",
            "params": [session_key, survey_id],
            "id": 1
        }
        response = requests.post(self.url, json=payload)
        if response.status_code == 200:
            return response.json().get("result", [])
        raise Exception(f"خطا در دریافت لیست سوالات: {response.text}")

    @staticmethod
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
    
    @staticmethod
    def save_question(report, question):
        instance = Question.objects.create(
            report=report, question=question
        )
        instance.save()
        return instance
    

def main():
    survey_dict = {}
    lime_instance = LimeSurvay()
    session_key = lime_instance.get_session_key()
    if session_key is not None:
        survey_list = lime_instance.get_list_surveys(session_key)
        for i in survey_list:
            survey_dict.update(i)
            report_instance = LimeSurvay.save_report(
                name=i["surveyls_title"], sid=i["sid"]
                )
            if report_instance is not None:
                questions = lime_instance.list_questions(session_key, survey_dict["sid"])
                for i in questions:
                    LimeSurvay.save_question(
                        report=report_instance, question=i["question"]
                        )
    else:
        raise Exception("error in session key")
    return lime_instance.release_session_key(session_key)