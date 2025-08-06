from django.views.decorators.http import require_POST
from django.http import JsonResponse

from apps.voice_process import utils


@require_POST
def transfer_voice_to_text(request):
    audio_file = request.FILES["audio_file"]
    if audio_file:
        in_memory_file = utils.StreamingFile(audio_file)
        response = utils.voice_process_api(voice=in_memory_file)
        if response is None:
            return JsonResponse({"error": "error"})
        else:
            save_voice = utils.save_voice(user=request.user, voice=audio_file, response=response)
            return JsonResponse({"success": response["text"]})
        
