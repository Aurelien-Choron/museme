from ShazamAPI import Shazam

def matching_algorithm(audio_filename):

    result = None
    mp3_file_content_to_recognize = open(audio_filename, 'rb').read()
 
    while result is None:
        shazam = Shazam(mp3_file_content_to_recognize)
        recognize_generator = shazam.recognizeSong()
        result = next(recognize_generator) # current offset & shazam response to recognize requests
    else:
        pass

    try:
        artist = result[-1]['track']['subtitle']
    except: 
        artist = 'Unknown'

    try:
        track_title = result[-1]['track']['title']
    except:
        track_title = 'Unknown'

    try:
        track_coverimg_hq = result[-1]['track']['images']['coverarthq']
    except:
        track_coverimg_hq = "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ac/No_image_available.svg/600px-No_image_available.svg.png"

    return artist, track_title, track_coverimg_hq
