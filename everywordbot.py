#!/usr/bin/env python
# encoding: utf-8
import tweepy
import os
import json
import random
from optparse import OptionParser

# --- CONFIGURATION ---
# The bot will finish 'en' entirely before moving to 'es', etc.
LANGS = ['en', 'es', 'fr', 'de', 'it']

# ADD THE SPECIFIC SLURS YOU WANT TO BLOCK HERE
BLOCKLIST = ["n-word-hard-r", "another-slur"] 

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

        # Setup Tweepy (Twitter API)
        auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
        auth.set_access_token(access_token, token_secret)
        self.twitter = tweepy.API(auth)

    def _get_state(self):
        """Loads the current language and line index from state.json."""
        if not os.path.isfile(self.state_file):
            return {"lang_idx": 0, "line_idx": 0}
        with open(self.state_file, 'r') as f:
            try:
                return json.load(f)
            except (ValueError, json.JSONDecodeError):
                return {"lang_idx": 0, "line_idx": 0}

    def _save_state(self, lang_idx, line_idx):
        """Writes current progress to state.json so it stays after restart."""
        with open(self.state_file, 'w') as f:
            json.dump({"lang_idx": lang_idx, "line_idx": line_idx}, f)

    def _is_safe(self, word):
        """Blocks specific slurs but allows profanity like 'fuck' or 'shit'."""
        clean_word = word.lower().strip()
        if clean_word in BLOCKLIST:
            return False
        return True

    def _get_line_from_file(self, lang, index):
        """Reads a specific line from the current language file."""
        file_path = os.path.join(self.source_folder, f"{lang}.txt")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Missing file: {file_path}")
            
        with open(file_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if i == index:
                    return line.strip()
        raise EOFError(f"End of {lang}.txt")

    def _random_point_in(self, bbox):
        lat = random.uniform(bbox[0], bbox[2])
        long = random.uniform(bbox[1], bbox[3])
        return (lat, long)

    def post(self):
        state = self._get_state()
        lang_idx = state["lang_idx"]
        line_idx = state["line_idx"]
        
        # Stop if we finished all 5 languages
        if lang_idx >= len(LANGS):
            print("Mission Accomplished: All language files are finished!")
            return

        current_lang = LANGS[lang_idx]
        
        try:
            status_str = self._get_line_from_file(current_lang, line_idx)
            
            # 1. Check if the word is on the blocklist
            if not self._is_safe(status_str):
                print(f"Skipping blocked word in {current_lang} at line {line_idx}")
                self._save_state(lang_idx, line_idx + 1)
                return self.post() # Try the next word immediately

            # 2. Add Prefix/Suffix if they exist
            if self.prefix: status_str = self.prefix + status_str
            if self.suffix: status_str = status_str + self.suffix
            if self.bbox: self.lat, self.long = self._random_point_in(self.bbox)

            # 3. Post to Twitter
            if self.dry_run:
                print(f"DRY RUN [{current_lang}] Line {line_idx}: {status_str}")
            else:
                # Note: update_status is for Tweepy 3.x. 
                # Use update_status(status=...) or client.create_tweet(text=...) for v2.
                self.twitter.update_status(status=status_str,
                                          lat=self.lat, long=self.long,
                                          place_id=self.place_id)
                print(f"POSTED [{current_lang}] Line {line_idx}: {status_str}")

            # 4. Save progress for the NEXT run (Stay in same language, next line)
            self._save_state(lang_idx, line_idx + 1)

        except EOFError:
            # Current language is empty, move to the NEXT language starting at Line 0
            print(f"FINISHED: All words in {current_lang}.txt are done.")
            new_lang_idx = lang_idx + 1
            
            if new_lang_idx < len(LANGS):
                print(f"MOVING TO: {LANGS[new_lang_idx]} starting at line 0...")
                self._save_state(new_lang_idx, 0)
                return self.post() # Try to post the first word of the new language
            else:
                print("All languages completed!")

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
    parser.add_option('--state_file', dest='state_file', default="state.json")
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
