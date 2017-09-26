from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.template import loader
from .common import *

# Create your views here.

from .models import Track, Playlist


def index(request):
    """
    View function for home page of site.
    """
    # Generate counts of some of the main objects
    num_tracks = Track.objects.count()
    num_playlists = Playlist.objects.count()
    # Available books (status = 'a')
    #num_instances_available = BookInstance.objects.filter(status__exact='a').count()
    #num_authors = Author.objects.count()  # The 'all()' is implied by default.

    # Render the HTML template index.html with the data in the context variable
    return render(
        request,
        'index.html',
        context={'num_tracks': num_tracks, 'num_playlists': num_playlists},
    )

def playlists(request):
    """
    View function for playlists page of site.
    """
    api = open_api(request.POST['mail'], request.POST['password'])
    library = load_personal_library()
    playlist_contents = api.get_all_user_playlist_contents()
    playlist_list = []
    for pl in playlist_contents:
        # for tr in pl.get('tracks'):

        p = Playlist(name=pl.get('name'), google_id=pl.get('id'), owner=request.POST['mail'])
        # p.save()
        p.stored_tracks = 0
        p.actual_tracks = len(pl.get('tracks'))
        playlist_list.append(p)
        if Playlist.objects.filter(google_id=p.google_id).count() > 0:
            stored_p = Playlist.objects.get(google_id=p.google_id);
            p.stored_tracks = stored_p.tracks.count()
    request.session['mail'] = request.POST['mail']
    request.session['password'] = request.POST['password']

    close_api()

    # Render the HTML template index.html with the data in the context variable
    return render(
        request,
        'playlists.html',
        context={'playlist_list': playlist_list},
    )

def backup_all(request):
    api = open_api(request.session['mail'], request.session['password'])
    library = load_personal_library()
    playlist_contents = api.get_all_user_playlist_contents()
    owner = request.session['mail']
    for pl in playlist_contents:
        playlist_name = pl.get('name')
        playlist_id = pl.get('id')
        playlist_tracks = pl.get('tracks')

        # skip empty and no-name playlists
        if not playlist_name: continue
        if len(playlist_tracks) == 0: continue

        # setup output files
        # playlist_name = u'a'

        # keep track of stats
        stats = create_stats()
        export_skipped = 0
        # keep track of songids incase we need to skip duplicates
        song_ids = []

        log('')
        log('============================================================')
        log(u'Exporting ' + str(len(playlist_tracks)) + u' tracks from '
            + playlist_name)
        log('============================================================')

        try:
            p = Playlist.objects.get(google_id=playlist_id)
        except Playlist.DoesNotExist:
            p = None

        if not p:
            p = Playlist(name='a', google_id=playlist_id, owner=owner)
            p.save()

        for tnum, pl_track in enumerate(playlist_tracks):
            track = pl_track.get('track')

            # we need to look up these track in the library
            if not track:
                library_track = [
                    item for item in library if item.get('id')
                                                in pl_track.get('trackId')]
                if len(library_track) == 0:
                    log(u'!! ' + str(tnum + 1) + repr(pl_track))
                    export_skipped += 1
                    continue
                track = library_track[0]

            result_details = create_result_details(track)

            # update the stats
            update_stats(track, stats)

            # export the track
            song_ids.append(result_details['songid'])
            try:
                t = Track.objects.get(google_id=result_details['songid'])
            except Track.DoesNotExist:
                t = None

            if not t:
                t = Track(title=result_details['title'], artist=result_details['artist'],
                          google_id=result_details['songid'], album=result_details['album'])
                t.save()

            p.tracks.add(t)

        # calculate the stats
        stats_results = calculate_stats_results(stats, len(playlist_tracks))

        # output the stats to the log
        log('')
        log_stats(stats_results)
        log(u'export skipped: ' + str(export_skipped))


    data = { 'done': 1 }
    close_api()
    return JsonResponse(data)

def backup(request):
    playlist_id = request.GET.get('playlists_id', None)
    data = {
        'num_tracks': 'Not available yet.'
    }
    return JsonResponse(data)

def restore(request):
    log('RESTORE')
    playlist_id = request.GET.get('playlist_id', None)
    try:
        p = Playlist.objects.get(google_id=playlist_id)
    except Playlist.DoesNotExist:
        return JsonResponse({'num_tracks': 'error'})
    # read the playlist into the tracks variable
    plog('Reading playlist... ')
    tracks = p.tracks.all()
    log('done. ' + str(len(tracks)) + ' tracks loaded.')

    # log in and load personal library
    api = open_api(request.session['mail'], request.session['password'])
    library = load_personal_library()

    # begin searching for the tracks
    log('===============================================================')
    log(u'Searching for songs from: ' + p.name)
    log('===============================================================')

    # gather up the song_ids and submit as a batch
    song_ids = []

    # collect some stats on the songs
    stats = create_stats()

    # time how long it takes
    start_time = time.time()

    track_count = 0

    # loop over the tracks that were read from the input file
    for track in tracks:

        # skip empty lines
        if not track:
            continue

        # parse the track info
        details = {}
        details['artists'] = track.artist
        details['album'] = track.album
        details['title'] = track.title
        details['songid'] = track.google_id

        # get playlist id
        playlist_id = p.google_id

        # at this point we should have a valid track
        track_count += 1

        # don't search if we already have a track id, add song
        if details['songid']:
            song_ids.append(details['songid'])
            continue

    total_time = time.time() - start_time

    log('===============================================================')
    log(u'Adding ' + str(len(song_ids)) + ' found songs to: ' + p.name)
    log('===============================================================')


    current_playlist_name = p.name

    # create the playlist and add the songs
    # playlist_id = api.create_playlist(current_playlist_name)

    added_songs = api.add_songs_to_playlist(playlist_id, song_ids)

    log(u' + ' + current_playlist_name + u' - ' + str(len(added_songs)) +
        u'/' + str(len(song_ids)) + ' songs')

    # log a final status

    log('===============================================================')
    log('   ' + str(len(song_ids)) + '/' + str(track_count) + ' tracks imported')
    log('')
    stats_results = calculate_stats_results(stats, len(song_ids))
    log_stats(stats_results)

    log('\nsearch time: ' + str(total_time))

    close_api()

    data = {
        'num_tracks': len(song_ids)
    }
    return JsonResponse(data)