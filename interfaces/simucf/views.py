from django.http import HttpResponse


def download_input_file(request):
    file_data = "some text"
    response = HttpResponse(file_data, content_type='application/text charset=utf-8')
    response['Content-Disposition'] = 'attachement; filename="simucf-input.txt"'
    return response

