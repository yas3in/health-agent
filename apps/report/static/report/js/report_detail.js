const BASE_URL = "https://voice-epi.ir" 

let question_list = document.querySelectorAll("#questions li");
let sendAnswers = document.querySelector("#sendAnswers");
let answerPromises = [];
sendAnswers.disabled = true;
let question_object = {}
question_list.forEach( (value, index) => {
question_object[index] = value.textContent;
})

let responses = [];
let report_sid = document.querySelector("#report_sid").textContent.trim();


function handleUserAnswer(audio) {
    const promise = transferVoiceToText(audio);
    answerPromises.push(promise);
}



function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            cookie = cookie.trim();
            if (cookie.startsWith(name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

const csrftoken = getCookie('csrftoken');
async function transferVoiceToText(voice) {
    const formData = new FormData();
    const question = document.querySelector("#question").textContent;
    formData.append("audio_file", voice);
    return fetch(BASE_URL + '/voice/speech-to-text/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrftoken
        },
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        responses.push({[question]: data["success"]});
        return data["success"];
    })
    .catch(error => {
        return error
    });
}

let next = document.querySelector("#next")
let counter = 0
let question = document.querySelector("#question")
question.innerHTML = question_object[counter]
next.addEventListener("click", ()=> {
    handleUserAnswer(audioFile)
    counter += 1;
    if (question_object[counter]) {
        question.innerHTML = question_object[counter]
        next.disabled = true
    } else {
        next.disabled = true
        sendAnswers.disabled = false;
        document.getElementById('startButton').disabled = true;
        
    }
})

let mediaRecorder;
let audioChunks = [];
let audioFile;

// دسترسی به میکروفن
navigator.mediaDevices.getUserMedia({ audio: true })
    .then(stream => {
        mediaRecorder = new MediaRecorder(stream);

        mediaRecorder.ondataavailable = event => {
            audioChunks.push(event.data);
        };

        mediaRecorder.onstop = () => {
            const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
            const audioUrl = URL.createObjectURL(audioBlob);

            // ایجاد URL برای پخش در پلیر (در صورت نیاز)
            document.getElementById('audioPlayer').src = audioUrl;

            // فعال کردن دکمه ارسال بعد از ضبط
            document.getElementById('next').disabled = false;

            // اضافه کردن فایل صوتی به input مخفی برای ارسال به بک‌اند
            audioFile = new File([audioBlob], 'recorded_audio.wav', { type: 'audio/wav' });
            const fileInput = document.getElementById('audioFileInput');
            const dataTransfer = new DataTransfer();
            dataTransfer.items.add(audioFile);
            fileInput.files = dataTransfer.files;
        };
    })
    .catch(error => {
        console.error("دسترسی به میکروفن با خطا مواجه شد:", error);
    });


// دکمه شروع ضبط
document.getElementById('startButton').addEventListener('click', () => {
    audioChunks = [];
    mediaRecorder.start();
    document.getElementById('startButton').disabled = true;
    document.getElementById('stopButton').disabled = false;
});


// دکمه متوقف کردن ضبط
document.getElementById('stopButton').addEventListener('click', () => {
    mediaRecorder.stop();
    document.getElementById('startButton').disabled = false;
    document.getElementById('stopButton').disabled = true;
});



sendAnswers.addEventListener("click", () => {
    sendAnswers.disabled = true;
    sendAnswers.textContent = "در حال ارسال گزارش... لطفا صبر کنید";

    Promise.all(answerPromises).then(() => {
        console.log("همه پاسخ‌ها آماده‌اند:", responses);

        sendReport(responses).then(() => {
            console.log("گزارش با موفقیت ارسال شد");
            window.location.href = "https://voice-epi.ir/reports/my-reports-list";
        }).catch(error => {
            console.error("خطا در ارسال گزارش:", error);
            sendAnswers.disabled = false;
            sendAnswers.textContent = "ارسال گزارش";
        });
    }).catch(error => {
        console.error("خطا در دریافت پاسخ‌ها:", error);
        sendAnswers.disabled = false;
        sendAnswers.textContent = "دریافت پاسخ ها با خطا مواجه شد";
    });
});


async function sendReport(data) {
    const url = `${BASE_URL}/reports/${report_sid}/`;
    let fd = new FormData()
    fd.append("report_sid", report_sid)
    fd.append("answers", data)
    console.log(data)
    console.log(report_sid);
    ;
    
    
    return fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrftoken
        },
        body: JSON.stringify({
        report_sid: report_sid,
        answers: data
    })
    }).then(response => {
        if (!response.ok) throw new Error("خطا در ارسال گزارش");
        return response.json();
    });
}
