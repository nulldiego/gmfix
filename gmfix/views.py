from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.template import loader
from .common import *
import requests

# Create your views here.

from .models import Track, Playlist, Entry


# compares two strings based only on their characters
def s_in_s(string1, string2):
    if not string1 or not string2:
        return False
    s1 = re.compile('[\W_]+', re.UNICODE).sub(u'', string1.lower())
    s2 = re.compile('[\W_]+', re.UNICODE).sub(u'', string2.lower())

    return s1 in s2 or s2 in s1


def index(request):
    """
    View function for home page of site.
    """
    # Generate counts of some of the main objects
    num_tracks = Track.objects.count()
    num_playlists = Playlist.objects.count()

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
    if api.is_authenticated():
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
                p.stored_tracks = stored_p.entry_set.count()
        request.session['mail'] = request.POST['mail']
        request.session['password'] = request.POST['password']

        close_api()

        # Render the HTML template index.html with the data in the context variable
        # playlist_list = []
        # p = Playlist(name="Hola", google_id="bla", owner="bla")
        # p.stored_tracks = 0
        # p.actual_tracks = 0
        # playlist_list.append(p)
        return render(
            request,
            'playlists.html',
            context={'playlist_list': sorted(playlist_list, key=lambda playlist: playlist.name)},
        )
    else:
        num_tracks = Track.objects.count()
        num_playlists = Playlist.objects.count()
        return render(
            request,
            'index.html',
            context={'num_tracks': num_tracks, 'num_playlists': num_playlists,
                     'error_message': "Unable to login, make sure you're using your Google Account and an app password."},
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

        Playlist.objects.filter(google_id=playlist_id).delete()

        p = Playlist(name=playlist_name, google_id=playlist_id, owner=owner)
        p.save()

        for tnum, pl_track in enumerate(playlist_tracks):
            track = pl_track.get('track')

            e = Entry(entry_id=pl_track.get('id'), playlist=p, position=tnum)
            e.save()

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

            e.track = t
            e.save()

        # calculate the stats
        stats_results = calculate_stats_results(stats, len(playlist_tracks))

        # output the stats to the log
        log('')
        log_stats(stats_results)
        log(u'export skipped: ' + str(export_skipped))

    data = {'done': 1}
    close_api()
    return JsonResponse(data)

def backup_interno(playlist_to_backup_id, mail, api):
    yield "start backup"
    playlist_contents = api.get_all_user_playlist_contents()
    owner = mail
    for pl in playlist_contents:
        playlist_name = pl.get('name')
        playlist_id = pl.get('id')
        # skip not desired playlists:
        if playlist_id != playlist_to_backup_id: continue
        yield "playlist found"
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

        Playlist.objects.filter(google_id=playlist_id).delete()
        yield "playlist deleted from db"

        p = Playlist(name=playlist_name, google_id=playlist_id, owner=owner)
        p.save()
        yield "playlist without tracks saved to db"

        for tnum, pl_track in enumerate(playlist_tracks):
            track = pl_track.get('track')

            e = Entry(entry_id=pl_track.get('id'), playlist=p, position=tnum)
            e.save()
            yield "entry saved"

            # we need to look up these track in the library
            if not track:
                if 'library' not in vars() and 'library' not in globals():
                    library = load_personal_library()
                    yield "library loaded"
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

            e.track = t
            e.save()
            yield "entry saved point 2"

        # calculate the stats
        stats_results = calculate_stats_results(stats, len(playlist_tracks))

        # output the stats to the log
        log('')
        log_stats(stats_results)
        log(u'export skipped: ' + str(export_skipped))
    return len(song_ids)


def backup(request):
    api = open_api(request.session['mail'], request.session['password'])
    return HttpResponse(backup_interno(request.GET.get('playlist_id', None), request.session['mail'], api))


def delete(request):
    api = open_api(request.session['mail'], request.session['password'])
    playlist_id = request.GET.get('playlist_id', None)
    api.delete_playlist(playlist_id)
    data = {
        'num_tracks': 0
    }
    close_api()
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
    entries = p.entry_set.all().order_by('position')
    log('done. ' + str(len(entries)) + ' entries loaded.')

    # log in and load personal library
    api = open_api(request.session['mail'], request.session['password'])

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
    entry_ids = []
    for entry in entries:
        entry_ids.append(entry.entry_id)
        track = entry.track
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

    if len(entry_ids) > 0:
        api.remove_entries_from_playlist(entry_ids)

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
    backup_interno(playlist_id, request.session['mail'], api)
    close_api()

    data = {
        'num_tracks': len(song_ids)
    }
    return JsonResponse(data)


def find(key, dictionary):
    for k, v in dictionary.items():
        if k == key:
            yield v
        elif isinstance(v, dict):
            for result in find(key, v):
                yield result
        elif isinstance(v, list):
            for d in v:
                for result in find(key, d):
                    yield result


def setlist(request):
    log('SETLIST.FM TO GPM')
    setlist_id = request.GET.get('setlist_id', None)
    playlist_name = request.GET.get('playlist_name', None)

    setlist_api_key = "895f215d-c072-4974-b639-7add77f120c9"

    url = 'https://api.setlist.fm/rest/1.0/setlist/' + setlist_id
    headers = {'Accept': 'application/json', 'x-api-key': setlist_api_key}

    # read the setlist into the tracks variable
    plog('Reading setlist... ')
    tracks = []

    r = requests.get(url, headers=headers)

    # Get .json Data
    data = r.json()

    print(data)

    log("VAMOS")

    sl_artist = data['artist']['name']

    sets = data['sets']

    for s in find('song', sets):
        for tr in s:
            print(tr)
            if 'cover' in tr:
                tracks.append(Track(title=tr['name'], artist=tr['cover']['name']))
            else:
                tracks.append(Track(title=tr['name'], artist=sl_artist))

    log('done. ' + str(len(tracks)) + ' tracks loaded.')

    # log in
    api = open_api(request.session['mail'], request.session['password'])

    # begin searching for the tracks
    log('===============================================================')
    log(u'Searching for songs from: ' + setlist_id)
    log('===============================================================')

    # gather up the song_ids and submit as a batch
    song_ids = []

    # collect some stats on the songs
    stats = create_stats()

    # time how long it takes
    start_time = time.time()

    track_count = 0

    # loop over the tracks that were read from the setlist
    for track in tracks:

        # parse the track info
        details = {}
        details['artist'] = track.artist
        details['title'] = track.title

        # at this point we should have a valid track
        track_count += 1

        # search for the song
        search_results = []
        dlog('search details: ' + str(details))

        # search the personal library for the track
        # lib_album_match = False
        # if details['artist'] and details['title'] and search_personal_library:
        #     lib_results = [item for item in library if
        #                    s_in_s(details['artist'], item.get('artist'))
        #                    and s_in_s(details['title'], item.get('title'))]
        #     dlog('lib search results: ' + str(len(lib_results)))
        #     for result in lib_results:
        #         if s_in_s(result['album'], details['album']):
        #             lib_album_match = True
        #         item = {}
        #         item[u'track'] = result
        #         item[u'score'] = 200
        #         search_results.append(item)

        # search all access for the track
        # if not lib_album_match:
        query = u''
        if details['artist']:
            query = details['artist']
        if details['title']:
            query += u' ' + details['title']
        if not len(query):
            query = track
        dlog('aa search query:' + query)
        aa_results = aa_search(query, 7)
        dlog('aa search results: ' + str(len(aa_results)))
        search_results.extend(aa_results)

        if not len(search_results):
            search_result = None
        else:
            top_result = search_results[0]
            # if we have detailed info, perform a detailed search
            if details['artist'] and details['title']:
                search_results = [item for item in search_results if
                                  s_in_s(details['title'], item['track']['title'])
                                  and s_in_s(details['artist'], item['track']['artist'])]
                dlog('detail search results: ' + str(len(search_results)))
                if len(search_results) != 0:
                    top_result = search_results[0]
            search_result = top_result

        # a details dictionary we can use for 'smart' searching
        smart_details = {}
        smart_details['title'] = details['title']
        smart_details['artist'] = details['artist']

        # if we didn't find anything strip out any (),{},[],<> from title
        match_string = '\[.*?\]|{.*?}|\(.*?\)|<.*?>'
        if not search_result and re.search(match_string, smart_details['title']):
            dlog('No results found, attempting search again with modified title.')
            smart_details['title'] = re.sub(match_string, '', smart_details['title'])
            # search for the song
            search_results = []
            dlog('search details: ' + str(details))

            # search the personal library for the track
            # lib_album_match = False
            # if details['artist'] and details['title'] and search_personal_library:
            #     lib_results = [item for item in library if
            #                    s_in_s(details['artist'], item.get('artist'))
            #                    and s_in_s(details['title'], item.get('title'))]
            #     dlog('lib search results: ' + str(len(lib_results)))
            #     for result in lib_results:
            #         if s_in_s(result['album'], details['album']):
            #             lib_album_match = True
            #         item = {}
            #         item[u'track'] = result
            #         item[u'score'] = 200
            #         search_results.append(item)

            # search all access for the track
            # if not lib_album_match:
            query = u''
            if details['artist']:
                query = details['artist']
            if details['title']:
                query += u' ' + details['title']
            if not len(query):
                query = track
            dlog('aa search query:' + query)
            aa_results = aa_search(query, 7)
            dlog('aa search results: ' + str(len(aa_results)))
            search_results.extend(aa_results)

            if not len(search_results):
                search_result = None
            else:
                top_result = search_results[0]
                # if we have detailed info, perform a detailed search
                if details['artist'] and details['title']:
                    search_results = [item for item in search_results if
                                      s_in_s(details['title'], item['track']['title'])
                                      and s_in_s(details['artist'], item['track']['artist'])]
                    dlog('detail search results: ' + str(len(search_results)))
                    if len(search_results) != 0:
                        top_result = search_results[0]
                search_result = top_result

        # if there isn't a result, try searching for the title only
        if not search_result and search_title_only:
            dlog('Attempting to search for title only')
            smart_details['artist'] = None
            smart_details['title_only_search'] = True
            # search for the song
            search_results = []
            dlog('search details: ' + str(details))

            # search the personal library for the track
            # lib_album_match = False
            # if details['artist'] and details['title'] and search_personal_library:
            #     lib_results = [item for item in library if
            #                    s_in_s(details['artist'], item.get('artist'))
            #                    and s_in_s(details['title'], item.get('title'))]
            #     dlog('lib search results: ' + str(len(lib_results)))
            #     for result in lib_results:
            #         if s_in_s(result['album'], details['album']):
            #             lib_album_match = True
            #         item = {}
            #         item[u'track'] = result
            #         item[u'score'] = 200
            #         search_results.append(item)

            # search all access for the track
            # if not lib_album_match:
            query = u''
            if details['artist']:
                query = details['artist']
            if details['title']:
                query += u' ' + details['title']
            if not len(query):
                query = track
            dlog('aa search query:' + query)
            aa_results = aa_search(query, 7)
            dlog('aa search results: ' + str(len(aa_results)))
            search_results.extend(aa_results)

            if not len(search_results):
                search_result = None
            else:
                top_result = search_results[0]
                # if we have detailed info, perform a detailed search
                if details['artist'] and details['title']:
                    search_results = [item for item in search_results if
                                      s_in_s(details['title'], item['track']['title'])
                                      and s_in_s(details['artist'], item['track']['artist'])]
                    dlog('detail search results: ' + str(len(search_results)))
                    if len(search_results) != 0:
                        top_result = search_results[0]
                search_result = top_result

        # check for a result
        if not search_result:
            log('No match for ' + smart_details['title'])
            continue

        # gather up info about result
        result = search_result.get('track')
        result_details = create_result_details(result)
        result_score = u' + '
        score_reason = u' '
        is_low_result = False
        # wrong song
        if ((details['title']
             and not s_in_s(details['title'], result_details['title']))
                or (not details['title']
                    and not s_in_s(track.title, result_details['title']))):
            score_reason += u'{T}'
            is_low_result = True

        if is_low_result:
            result_score = u' - '

        result_score = (result_score, score_reason)

        # if the song title doesn't match after a title only search, skip it
        (score, reason) = result_score
        if '{T}' in reason and 'title_only_search' in smart_details:
            log('No match for ' + smart_details['title'])
            continue

        update_stats(result, stats)

        # add the song to the id list
        song_ids.append(result_details['songid'])

    total_time = time.time() - start_time

    current_playlist_name = playlist_name

    # create the playlist and add the songs
    playlist_id = api.create_playlist(current_playlist_name)

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
