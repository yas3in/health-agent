import OpenAI from "openai";
const client = new OpenAI({
    apiKey: "aa-jTQuoFCLBel2Wffo3ojPLmIK4t3wwXJxgfnxLHuQrkbrIuE0",
    baseURL: "https://api.avalai.ir/v1", // نقطه پایانی API AvalAI
});

const response = await client.responses.create({
  model: "gpt-4o",
  input: "فقط بنویس سلام خوبی یاسین جون",
});

console.log(response.output_text);