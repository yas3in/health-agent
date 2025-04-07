from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_POST
from django.http import JsonResponse

from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

@require_POST
def voice_process(request):
    audio_file = request.FILES["audio_file"]
    form = request.kwargs
    print(request)
    file_path = default_storage.save(f'audios/{audio_file.name}', ContentFile(audio_file.read()))
    return JsonResponse({'message': 'فایل با موفقیت ذخیره شد', 'file_path': file_path})
