#!/usr/bin/env python
# encoding: utf-8
import tweepy
import os
import json
import random
from optparse import OptionParser

# --- CONFIGURATION ---
LANGS = ['en', 'es', 'fr', 'de', 'it']
# Add the specific slurs you want to hard-block here
BLOCKLIST = ["n-word-hard-r", "other-slur-here"] 

class EverywordBot(object):

    def __init__(self, consumer_key, consumer_secret,
                 access_token, token_secret,
                 source_folder, state_file,
                 lat=None, long=None, place_id=None,
                 prefix=None, suffix=None, bbox=None,
                 dry_run=False):
        self.source_folder = source_folder
        self.state_file = state_file
        self.lat = lat
        self.long = long
        self.place_id = place_id
        self.prefix = prefix
        self.suffix = suffix
        self.bbox = bbox
        self.dry_run = dry_run

        # Setup Tweepy
        auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
        auth.set_access_token(access_token, token_secret)
        self.twitter = tweepy.API(auth)

    def _get_state(self):
        """Loads the current language index and line index from JSON."""
        if not os.path.isfile(self.state_file):
            return {"lang_idx": 0, "line_idx": 0}
        with open(self.state_file, 'r') as f:
            try:
                return json.load(f)
            except ValueError:
                return {"lang_idx": 0, "line_idx": 0}

    def _save_state(self, lang_idx, line_idx):
        """Saves progress so it persists after the bot restarts."""
        with open(self.state_file, 'w') as f:
            json.dump({"lang_idx": lang_idx, "line_idx": line_idx}, f)

    def _is_safe(self, word):
        """Blocks slurs but allows general profanity like 'fuck' or 'shit'."""
        clean_word = word.lower().strip()
        if clean_word in BLOCKLIST:
            return False
        return True

    def _get_line_from_file(self, lang, index):
        """Reads a specific line from the language's text file."""
        file_path = os.path.join(self.source_folder, f"{lang}.txt")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Missing file: {file_path}")
            
        with open(file_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if i == index:
                    return line.strip()
        raise EOFError(f"Reached end of list for {lang}")

    def _random_point_in(self, bbox):
        lat = random.uniform(bbox[0], bbox[2])
        long = random.uniform(bbox[1], bbox[3])
        return (lat, long)

    def post(self):
        state = self._get_state()
        lang_idx = state["lang_idx"]
        line_idx = state["line_idx"]
        
        # Determine current language
        current_lang = LANGS[lang_idx]
        
        try:
            status_str = self._get_line_from_file(current_lang, line_idx)
            
            # Filter Check
            if not self._is_safe(status_str):
                print(f"Skipping blocked word in {current_lang}: [REDACTED]")
                # Increment line and try again recursively
                self._save_state(lang_idx, line_idx + 1)
                return self.post()

            # Formatting
            if self.prefix: status_str = self.prefix + status_str
            if self.suffix: status_str = status_str + self.suffix
            if self.bbox: self.lat, self.long = self._random_point_in(self.bbox)

            if self.dry_run:
                print(f"DRY RUN [{current_lang}]: {status_str}")
            else:
                self.twitter.update_status(status=status_str,
                                          lat=self.lat, long=self.long,
                                          place_id=self.place_id)
                print(f"POSTED [{current_lang}]: {status_str}")

            # Update indices for next run
            # Logic: Move to next language. If we've done all languages, move to next line.
            next_lang_idx = (lang_idx + 1) % len(LANGS)
            next_line_idx = line_idx
            if next_lang_idx == 0:
                next_line_idx += 1
                
            self._save_state(next_lang_idx, next_line_idx)

        except EOFError:
            print(f"Finished all words in {current_lang}. checking next...")
            # If one lang finishes, you might want to skip it in the future, 
            # but for now, we'll just stop.
            pass

def _csv_to_float_list(csv):
    return list(map(float, csv.split(',')))

if __name__ == '__main__':
    def _get_comma_separated_args(option, opt, value, parser):
        setattr(parser.values, option.dest, _csv_to_float_list(value))

    parser = OptionParser()
    parser.add_option('--consumer_key', dest='consumer_key')
    parser.add_option('--consumer_secret', dest='consumer_secret')
    parser.add_option('--access_token', dest='access_token')
    parser.add_option('--token_secret', dest='token_secret')
    parser.add_option('--source_folder', dest='source_folder', default="languages")
    parser.add_option('--state_file', dest='state_file', default="bot_state.json")
    parser.add_option('--lat', dest='lat')
    parser.add_option('--long', dest='long')
    parser.add_option('--prefix', dest='prefix')
    parser.add_option('--suffix', dest='suffix')
    parser.add_option('-n', '--dry_run', dest='dry_run', action='store_true')

    (options, args) = parser.parse_args()

    bot = EverywordBot(options.consumer_key, options.consumer_secret,
                       options.access_token, options.token_secret,
                       options.source_folder, options.state_file,
                       options.lat, options.long, None,
                       options.prefix, options.suffix, None,
                       options.dry_run)
    bot.post()
