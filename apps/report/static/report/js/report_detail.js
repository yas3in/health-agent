let questions = document.querySelectorAll("#questions li")

question_object = {}

questions.forEach( (value, index) => {
    question_object[index] = value.textContent;
});

console.log(question_object);


