function handler(audioFile) {
    let response = transferVoiceToText(audioFile)
    console.log(response);
    
}


function listToObject(params) {
    let question_list = document.querySelectorAll("#questions li")
    let question_object = {}
    question_list.forEach( (value, index) => {
    question_object[index] = value.textContent;
    return question_object
})}


function transferVoiceToText(voice) {
    const API_KEY = "aa-jTQuoFCLBel2Wffo3ojPLmIK4t3wwXJxgfnxLHuQrkbrIuE0"
    const formData = new FormData();
    formData.append("file", voice);
    formData.append("model", "whisper-1");
    fetch('https://api.avalai.com/v1/speech-to-text', {  // مثال آدرس، آدرس دقیق API رو از مستندات بردار
        method: 'POST',
        headers: {
            'Authorization': 'Bearer ' + API_KEY
        },
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        return data.text
    })
    .catch(error => {
        return error
    });
}

function nextQuestion(params) {    
    let next = document.querySelector("#next")
    let counter = 0
    let question = document.querySelector("#question")
    question.innerHTML = question_object[counter]
    next.addEventListener("click", ()=> {
        counter += 1;
        if (question_object[counter]) {
            question.innerHTML = question_object[counter]
        } else {
            next.disabled = true
            console.log("finish");      
        }
    })
}

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
            handler(audioFile)
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
