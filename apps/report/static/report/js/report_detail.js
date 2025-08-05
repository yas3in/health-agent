let question_list = document.querySelectorAll("#questions li");
let sendAnswers = document.querySelector("#sendAnswers");
let answerPromises = [];
sendAnswers.disabled = true;
let question_object = {}
question_list.forEach( (value, index) => {
question_object[index] = value.textContent;
})

let responses = [];
let report_sid = document.querySelector("#report_sid").textContent;


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
    return fetch('http://127.0.0.1:8000/voice/speech-to-text/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrftoken
        },
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        responses.push({question: question, asnwer: data["success"]});
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
        console.log(responses);
        
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
            window.location.href = "/next-page";
        }).catch(error => {
            console.error("خطا در ارسال گزارش:", error);
            // پیام خطا و فعال کردن دوباره دکمه در صورت نیاز
            sendAnswers.disabled = false;
            sendAnswers.textContent = "ارسال گزارش";
        });
    }).catch(error => {
        console.error("خطا در دریافت پاسخ‌ها:", error);
        // اگر Promiseها reject شدن، هم میتونی دکمه رو فعال کنی یا پیام مناسب بدی
        sendAnswers.disabled = false;
        sendAnswers.textContent = "ارسال گزارش";
    });
});