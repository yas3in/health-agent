let questions = document.querySelectorAll("#questions li")

question_object = {}

questions.forEach( (value, index) => {
    question_object[index] = value.textContent;
});


let next = document.querySelector("#next")

let counter = 0
let question = document.querySelector("#question")
question.innerHTML = question_object[counter]
next.addEventListener("click", ()=> {
    // transferVoiceToText(voice, question_object[counter])
    counter += 1;
    if (question_object[counter]) {
        question.innerHTML = question_object[counter]
        
    } else {
        next.disabled = true
        console.log("finish");
        
    }
})

function transferVoiceToText(voice, question) {
 
}