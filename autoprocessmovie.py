#!/usr/bin/python

import time
import re
import urllib
import urllib2
import json
import os
import sys

from configobj import ConfigObj

script_path           = os.path.dirname(sys.argv[0])
config_full_path      = os.path.join(script_path, 'autoprocessmovie.ini')
config_obj            = ConfigObj(config_full_path)

logging_enable        = config_obj.get('Preferences').as_bool('logging_enable')
log_file              = config_obj['Preferences']['log_file']
media_library_path    = config_obj['Preferences']['media_library_path']
media_file_types      = config_obj.get('Preferences').as_list('media_file_types')
sub_file_types        = config_obj.get('Preferences').as_list('sub_file_types')
dest_dir_exist_abort  = config_obj.get('Preferences').as_bool('dest_dir_exist_abort')
move_media            = config_obj.get('Preferences').as_bool('move_media')
use_sample            = config_obj.get('Preferences').as_bool('use_trailer')
src_trailer_regex     = config_obj.get('Preferences').as_list('src_trailer_regex')
trailer_suffix        = config_obj['Preferences']['trailer_suffix']
api_key               = config_obj['Preferences']['api_key']
delete_chars          = config_obj['Preferences']['delete_chars']
src_path              = config_obj['Preferences']['src_path_override']

tmdb_url              = 'https://api.themoviedb.org/3/search/movie?'
omdb_url              = 'http://www.omdbapi.com/?'
dir_name_regex        = '(.[^\(]*).*([0-9]{4})[ |\)]'
source_regex          = '\\b(dvdrip|dvdr|dsr|dsrip|dthrip|dvbrip|hdtv|pdtv|tvrip|hdtvrip|vodrip|vodr|web.?dl|web.?rip|web.?cap|bdrip|brrip|blu.?ray|bdr|ddc|camrip|cam|ts|telesync|pdvd|hdrip|r5.?line|r5|scr|screener|dvdscr|dvdscreener|bdscr|ppv|ppvrip|tc|telecine)\\b'
media_library_path    = os.path.normpath(media_library_path)
src_path              = os.path.normpath(src_path)
log_file              = os.path.join(script_path, log_file)

def WriteLog(msg):
    log_line = time.strftime('%Y-%m-%d ') + time.strftime('%H:%M:%S - ') + msg
    if logging_enable:
        with open(log_file, 'a') as f:
            f.write(log_line + '\n')
    print msg
    
def RemoveInvalidChars(value):
    for c in delete_chars:
        value = value.replace(c,'')
    return value;

def GetMediaNameToProcess():
    src_media_dir_name = os.path.basename(src_path.replace('.', ' ').replace('_',' '))
    WriteLog('src_media_dir_name: ' + src_media_dir_name)
    match_res = re.search(dir_name_regex, src_media_dir_name)
    if match_res:
        return match_res.group(1).strip(), match_res.group(2).strip()
    else:
        return None, None
        
def GetMediaSourceToProcess(src_full_path):
    src_full_path = os.path.basename(src_full_path.replace('.', ' ').replace('_',' '))
    WriteLog('GetMediaSourceToProcess: ' + src_full_path)
    match_res = re.search(source_regex, src_full_path, re.IGNORECASE)
    if match_res:
        return '-' + match_res.group(1).strip().lower()
    else:
        return ''

def GetJsonTMDB(name_from_dir, year_from_dir):
    params = urllib.urlencode( { 'query': name_from_dir, 'year': year_from_dir, 'api_key': api_key } )
    response = ''
    #WriteLog(tmdb_url + params)
    try:
        response = urllib2.urlopen(tmdb_url + params)
    except urllib2.HTTPError, e:
        #WriteLog('Server Error: ' + e.code)
        WriteLog('Server Error: ' + str(e.code))
    except urllib2.URLError, e:
        WriteLog('Connection Err: ' + str(e.reason))
        #WriteLog('Server Error: ' + e.read())
    else:
        return json.load(response)

def GetJsonOMDB(name_from_dir, year_from_dir):
    params = urllib.urlencode( { 't': name_from_dir, 'y': year_from_dir } )
    response = ''
    #WriteLog(omdb_url + params)
    try:
        response = urllib2.urlopen(omdb_url + params)
    except urllib2.HTTPError, e:
        #WriteLog('Server Error: ' + e.code)
        WriteLog('Server Error: ' + str(e.code))
    except urllib2.URLError as e:
        #WriteLog('Connection Error: ' + e.reason)
        WriteLog('Connection Err: ' + str(e.reason))
    else:
        return json.load(response)                
        
def DoCopyMove(src, dst):
    import shutil
    op = 'move' if move_media else 'copyfile'
    getattr(shutil, op)(src, dst)

def main():
    WriteLog('-' * len(src_path))
    WriteLog(src_path)
    WriteLog('-' * len(src_path))

    name_from_dir, year_from_dir = GetMediaNameToProcess()
    if name_from_dir and year_from_dir:
        WriteLog("Movie '{0}' with year '{1}' guessed from directory".format(name_from_dir, year_from_dir))
        actual_movie_name = ''
        actual_year = ''
        results_found = False
        
        if not results_found:
            return_json = GetJsonTMDB(name_from_dir, year_from_dir)
            if return_json:
                if (int(return_json['total_results']) > 0):
                    WriteLog("Using results from TMDB")
                    actual_movie_name = return_json['results'][0]['title']
                    actual_year = return_json['results'][0]['release_date']
                    results_found = True
                else:
                    WriteLog("No results from TMDB.")
            else:
                WriteLog("No response from TMDB.")
            
        if not results_found:
            return_json = GetJsonOMDB(name_from_dir, year_from_dir)
            if return_json:
                if return_json['Response'] == 'True':
                    if return_json['Type'] == 'movie':
                        WriteLog("Using results from OMDB")
                        actual_movie_name = return_json['Title']
                        actual_year = return_json['Year']
                        results_found = True
                    else:
                        WriteLog("No results from OMDB.")
                else:
                    WriteLog("No results from OMDB.")
            else:
                WriteLog("No response from OMDB.")
                    
        if results_found:
            sanitized_movie_name = RemoveInvalidChars(actual_movie_name)
            sanitized_movie_name = "{0} ({1})".format(sanitized_movie_name, actual_year[0:4])
            WriteLog("Trying to rename movie to '{0}'".format(sanitized_movie_name))
            dest_dir = os.path.join(media_library_path, sanitized_movie_name)
            if os.path.isdir(dest_dir):
                WriteLog("Destination folder '{0}' already exists".format(dest_dir))
                dest_dir_exists = True
            else:
                WriteLog("Creating destination folder '{0}'".format(dest_dir))
                dest_dir_exists = False
            if dest_dir_exist_abort and dest_dir_exists:
                WriteLog("Aborting on dest_dir_exist = true")
                return 4
            else:
                media_to_move = '', 0
                trailer_src_path = ''
                sub_src_paths = []
                for cur_path, dirs, files in os.walk(src_path):
                    WriteLog("Searching in '{0}'".format(cur_path))    
                    for f in files:
                        src_fullpath = os.path.join(cur_path, f)
                        base, ext = os.path.splitext(f)
                        if ext in media_file_types:
                            WriteLog("{0} Media found: '{1}'".format('-' * 4, f))
                            sample_found = [s for s in src_trailer_regex if re.search(s, base, re.IGNORECASE)]
                            if len(sample_found) > 0:
                                if use_sample:
                                    WriteLog("{0} Using sample file '{1}'".format('-' * 8, f))
                                    trailer_src_path = src_fullpath
                                else:
                                    WriteLog("{0} Ignoring sample file '{1}'".format('-' * 8, f))
                            else:
                                if os.path.getsize(src_fullpath) > media_to_move[1]:
                                    WriteLog("{0} Using media file '{1}'".format('-' * 8, f))
                                    media_to_move = src_fullpath, os.path.getsize(src_fullpath)
                                else:
                                    WriteLog("{0} Ignoring media file '{1}'".format('-' * 8, f))
                        else:
                            WriteLog("{0} Ignoring file '{1}'".format('-' * 4, f))
                        if ext in sub_file_types:
                            WriteLog("{0} Sub found: '{1}'".format('-' * 4, f))
                            sub_src_paths.append(src_fullpath)
                if media_to_move[1] > 0:
                    os.mkdir(dest_dir)
                    ext = os.path.splitext(media_to_move[0])[1]
                    media_source = GetMediaSourceToProcess(os.path.splitext(media_to_move[0])[0])
                    WriteLog("media_source: {0}".format(media_source))
                    DoCopyMove(media_to_move[0], os.path.join(dest_dir, sanitized_movie_name + str(media_source) + ext))
                    if trailer_src_path != '':
                        ext = os.path.splitext(trailer_src_path)[1]
                        DoCopyMove(trailer_src_path, os.path.join(dest_dir, sanitized_movie_name + str(media_source) + str(trailer_suffix) + ext))
                    if len(sub_src_paths) > 0:
                        for sub_src_path in sub_src_paths:
                            ext = os.path.splitext(sub_src_path)[1]
                            DoCopyMove(sub_src_path, os.path.join(dest_dir, sanitized_movie_name + str(media_source) + ext))
                else:
                    WriteLog("No media found")
        else:
            WriteLog("Cannot find movie: " + return_json)
            return 1
    else:
        WriteLog("Cannot guess media name from directory: '{0}'".format(src_path))
        return 3
    WriteLog("Successfully processed to '{0}'".format(dest_dir))
    return 0

if __name__ == '__main__':
    if len(sys.argv) > 1:
        src_path = sys.argv[1]
    sys.exit(main())