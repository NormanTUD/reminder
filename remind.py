import argparse
import matplotlib.pyplot as plt
import webbrowser

parser = argparse.ArgumentParser(description='Reminder program')

# Add an argument to disable the GUI and run the check code every 5 seconds
parser.add_argument('--headless', action='store_true', help='disable the GUI and run the check code every 5 seconds')
parser.add_argument('--debug', action='store_true', default=False, help='enable debug mode')

args = parser.parse_args()

import threading
import easygui
import calendar
import tty
import re
import termios
import traceback
from pprint import pprint
from timefhuman import timefhuman
import sys
import readline
import os
import tempfile
import locale
import sqlite3
import os
import datetime

from datetime import timezone

utc_dt = datetime.datetime.now(timezone.utc) # UTC time
dt = utc_dt.astimezone() # local time

timezone_adjustment = 2 * 3600 # difference to GMT, currently set to germany/berlin, only relevant for debugging

import readline
import rlcompleter


def read_input_without_history(prompt='> '):
    # Save the current terminal settings
    old_settings = termios.tcgetattr(sys.stdin)

    try:
        # Set the terminal to raw mode
        tty.setraw(sys.stdin.fileno())

        # Print the prompt and read the input
        sys.stdout.write(prompt)
        sys.stdout.flush()
        input_str = ''
        while True:
            ch = sys.stdin.read(1)
            if ch == '\r' or ch == '\n':
                sys.stdout.write('\r\n')
                break
            elif ch == '\x03':  # Ctrl-C
                return False
            elif ch == '\x04':  # Ctrl-D
                raise EOFError
            else:
                input_str += ch
                sys.stdout.write(ch)
                sys.stdout.flush()

        return input_str

    finally:
        # Restore the terminal settings
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)


current_year = datetime.datetime.now().year
current_month = datetime.datetime.now().month
current_day = datetime.datetime.now().day

orig_settings = termios.tcgetattr(sys.stdin)
# Set up the completer
completer = rlcompleter.Completer()

# Set the completer for the readline module

def complete_names(text, state):
    names = ["list", "help", "test", "rm", "cal", "calendar", "chose", "choose", "exit", "quit", "q", "stat", "debug"]
    # Get all possible completions that match the current input
    matching_names = [name for name in names if name.startswith(text)]

    if len(matching_names):
        if text.startswith("rm"):
            return autocomplete_rm(text, state)
        else:
            return matching_names[state]

    return None

def autocomplete_rm(text, state):
    conn = sqlite3.connect(db_file)
    c = conn.cursor()

    c.execute("SELECT id FROM events")
    rows = c.fetchall()

    matching_rows = [row[0] for row in rows if str(row[0]).startswith(text)]

    if state < len(matching_rows):
        return f"{matching_rows[state]}"
    else:
        return None

readline.set_completer_delims(" \t\n")
readline.parse_and_bind("tab: complete")
readline.set_completer(complete_names)

# Now you can use tab completion in the Python shell

# Set the path for the SQLite3 database file
db_file = os.path.expanduser('~/.calendar.sqlite3')
history_file = os.path.expanduser('~/.reminder_history')
if os.path.exists(history_file):
    readline.read_history_file(history_file)


import datetime
import time
import tkinter as tk
from tkinter.messagebox import showinfo

def set_event_has_been_shown(event_id):
    debug(f"set_event_has_been_shown({event_id})")
    conn = sqlite3.connect(db_file)
    c = conn.cursor()

    query = '''
        UPDATE events
        SET has_been_shown = 1
        WHERE id = ?
    '''

    debug(query)

    c.execute(query, (event_id,))
    conn.commit()
    conn.close()

def open_urls_with_firefox (msg):
    url_pattern = re.compile(r'(https?://\S+)')

    # Retrieve all URLs from msg using the regular expression pattern
    urls = url_pattern.findall(msg)

    # Open a Firefox instance for each URL
    for url in urls:
        webbrowser.get('firefox').open(url)



def human_to_crontab(human_str):
    days_of_week = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]
    match = re.match(r"every (\b\w+\b) at (\d{1,2}):(\d{2})", human_str)

    if not match:
        raise ValueError("Invalid input string format")
    day_of_week, hour, minute = match.groups()
    day_of_week = days_of_week.index(day_of_week.lower())
    return f"{minute} {hour} * * {day_of_week}"


def show_upcoming_events_with_gui ():
    # Get the current time
    now = datetime.datetime.now()

    # Get the events within the next 5 minutes
    start_time = now # + datetime.timedelta(minutes=-5)
    end_time = now + datetime.timedelta(minutes=5)

    start_time = int(datetime.datetime.timestamp(start_time))
    end_time = int(datetime.datetime.timestamp(end_time))

    events = get_events(start_time, end_time, 1)

    # Display the events in a message box
    if events:
        root = tk.Tk()
        root.withdraw()
        for event in events:
            t = from_unix_timestamp(event["dt"])
            msg = f'{t}: {event["description"]}'
            set_event_has_been_shown(event['id'])
            print(f"Upcoming event: {msg}")
            open_urls_with_firefox(msg)
            showinfo('Upcoming Event', msg)
            # Set the has_been_shown flag to 1 for this event
            time.sleep(2)
        root.destroy()

def initialize_table ():
    # Define the table for events
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dt INTEGER NOT NULL,
            description TEXT NOT NULL,
            weeks_multiplier INTEGER DEFAULT 0,
            has_been_shown INTEGER DEFAULT 0
        )
    ''')
    conn.commit()

    c = conn.cursor()
    c.execute('''
    CREATE TABLE IF NOT EXISTS crontab (
        minute TEXT NOT NULL,
        hour TEXT NOT NULL,
        day_of_month TEXT NOT NULL,
        month TEXT NOT NULL,
        day_of_week TEXT NOT NULL,
        text TEXT NOT NULL
    );
    ''')
    conn.commit()

    conn.close()

initialize_table()

def insert_crontab(crontab_str, text):
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    debug(crontab_str)
    i = re.split(r"\s+", crontab_str)
    j = "'" + ("', '".join(i)) + "'"
    query = f'''INSERT INTO crontab (minute, hour, day_of_month, month, day_of_week, text) VALUES ({j}, '{text}')'''
    debug(query)
    try:
        c.execute(query)
        conn.commit()
        conn.close()
        event_id = c.lastrowid
    except Exception as e:
        error(e, 0)
        error("Crontab-String: " + crontab_str, 0)
        error("Query: " + query, 0)

    return event_id


def insert_event(date, description, weeks_multiplier=1):
    debug(f"insert_event({date}, {description}, {weeks_multiplier})")

    conn = sqlite3.connect(db_file)
    c = conn.cursor()

    # Check if there is already an event with the same description at the same time
    c.execute("SELECT COUNT(*) FROM events WHERE dt = ? AND description = ?", (date, description))
    count = c.fetchone()[0]

    if count == 0:
        c.execute('''
            INSERT INTO events (dt, description, weeks_multiplier)
            VALUES (?, ?, ?)
        ''', (date, description, weeks_multiplier))
        conn.commit()

        event_id = c.lastrowid
        event_id = c.lastrowid
        dt = datetime.datetime.fromtimestamp(date).strftime('%Y-%m-%d %H:%M')

        if date < datetime.datetime.now().timestamp():
            warning(f"{dt} is in the past")

        ok(f"Inserted event '{description}' on {dt} with id: {event_id}")
    else:
        warning("An event with the same description at the same time already exists. Skipping insertion.")

        conn.close()
        return None

    conn.close()

    return event_id


def datetime_to_unix_timestamp(dt_string):
    # Parse the datetime string into a datetime object
    dt = datetime.datetime.strptime(dt_string, '%Y-%m-%d %H:%M:%S')

    # Get the Unix timestamp for the datetime object
    unix_timestamp = int(dt.timestamp())

    return unix_timestamp

def from_unix_timestamp(unix_timestamp):
    dt = datetime.datetime.fromtimestamp(unix_timestamp)
    return dt.strftime('%Y-%m-%d %H:%M:%S')

def get_event_dates(year, month):
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    start_date = datetime.date(year, month, 1)
    if month == 12:
        end_date = datetime.date(year+1, 1, 1)
    else:
        end_date = datetime.date(year, month+1, 1)
    query = f'''
    SELECT DISTINCT dt FROM events WHERE 1
    OR (
        weeks_multiplier > 0 -- Repeating event
        -- AND has_been_shown = 0 -- Has not been shown yet
        AND strftime('%s', 'now') - dt >= weeks_multiplier * 604800 -- Repeating interval has passed
        AND strftime('%s', 'now', '{start_date}') - dt >= 0 -- Event starts before end of day
        AND (strftime('%s', 'now', '{start_date}') - dt) % (weeks_multiplier * 604800) = 0
    ) -- Event is due today based on repeating interval
    '''
    debug(query)
    c.execute(query)
    debug(query)
    debug((start_date, end_date))
    rows = c.fetchall()
    event_dates = [datetime.datetime.strptime(from_unix_timestamp(row[0]), '%Y-%m-%d %H:%M:%S').date() for row in rows]

    event_days = [date.day for date in event_dates]

    conn.close()

    return event_days

# Define a function for getting all events within a date range
def get_events(start_date, end_date, only_unshown=0):
    conn = sqlite3.connect(db_file)
    c = conn.cursor()


    only_unshown_query = "1"
    if only_unshown:
        only_unshown_query = " has_been_shown = '0' "

    query = f'''
        SELECT id, dt, description, weeks_multiplier, has_been_shown
        FROM events
        WHERE dt >= ? AND dt <= ?
    '''

    debug("start: " + str(start_date))
    debug("end: " + str(end_date))
    #debug("start: " + str(datetime.datetime.utcfromtimestamp(start_date).strftime('%Y-%m-%d %H:%M:%S')) + timezone_adjustment)
    #debug("end:   " + str(datetime.datetime.utcfromtimestamp(end_date).strftime('%Y-%m-%d %H:%M:%S')) + timezone_adjustment)

    debug(query)
    debug((start_date, end_date))

    c.execute(query, (start_date, end_date))

    rows = c.fetchall()
    events = []

    for row in rows:
        event = {
            'id': row[0],
            'dt': row[1],
            'description': row[2],
            'weeks_multiplier': row[3],
            'has_been_shown': row[4]
        }

        if only_unshown == 0 or only_unshown and not event["has_been_shown"]:
            events.append(event)
    conn.close()
    return events

# Define a function for getting all events on a specific date
def get_events_on_date(year, month, day):
    ymd = f"{year:0>4}-{month:0>2}-{day:0<2}"

    start = f"{ymd} 00:00:00"
    end = f"{ymd} 23:59:59"

    start_timestamp = int(datetime.datetime.strptime(start, '%Y-%m-%d %H:%M:%S').timestamp())
    if current_day == day and current_year == year and current_month == month:
        end_timestamp = int(time.time())
    end_timestamp = int(datetime.datetime.strptime(end, '%Y-%m-%d %H:%M:%S').timestamp())

    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    query = f'''
        SELECT id, dt, description, weeks_multiplier
        FROM events
        WHERE
        (dt >= {start_timestamp} and dt <= {end_timestamp})
        OR (
            weeks_multiplier > 0 -- Repeating event
            -- AND has_been_shown = 0 -- Has not been shown yet
            AND abs((strftime('%s', 'now') - dt) / (weeks_multiplier * 604800)) >= 600 -- Repeating interval has passed, interval allowance is 600 sec by default
            AND ({start_timestamp} - dt) >= 0 -- Event starts before end of day
            AND ({start_timestamp} - dt) % (weeks_multiplier * 604800) = 0
        ) -- Event is due today based on repeating interval
        ORDER BY dt asc, description asc, id asc
    '''

    debug(query)
    c.execute(query)
    rows = c.fetchall()
    events = []
    for row in rows:
        event = {
                'id': row[0],
                'date': row[1],
                'description': row[2],
                'weeks_multiplier': row[3],
        }

        events.append(event)
    conn.close()
    return events

# Define a function for getting all events that occur on a specific weekday
def get_events_on_weekday(weekday):
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    c.execute('''
        SELECT id, datetime, description, weeks_multiplier
        FROM events
        WHERE strftime('%w', date) = ?
    ''', (weekday,))
    rows = c.fetchall()
    events = []
    for row in rows:
        event = {
                'id': row[0],
                'date': row[1],
                'description': row[2],
                'weeks_multiplier': row[3]
                }
        events.append(event)
    conn.close()
    return events

def print_events_on_date(year, month, day):
    target_date = datetime.date(year, month, day)
    events = get_events_on_date(year, month, day)

    if len(events) == 0:
        print(f"No events on {target_date}")
    else:
        print(f"Events on {target_date}:")
        for event in events:
            date = event['date']
            
            date_obj = datetime.datetime.fromtimestamp(date)
            date = date_obj.strftime('%Y-%m-%d %H:%M:%S')

            print(f"- {event['description']} ({bcolors.OKGREEN}{date}{bcolors.ENDC}, id: {event['id']})")
    print("")


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    RED  = '\033[91m'
    ONGREEN = '\033[0;102m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    BLINK = '\033[33;5m'

def warning (msg):
    print(f"WARNING: {bcolors.WARNING}{msg}{bcolors.ENDC}")
    stack_trace = traceback.extract_tb(sys.exc_info()[2])
    # Print the modified stack trace
    traceback.print_list(stack_trace)

def debug (msg):
    if not args.debug:
        return
    print(f"{bcolors.HEADER}{msg}{bcolors.ENDC}")
    stack_trace = traceback.extract_tb(sys.exc_info()[2])
    # Print the modified stack trace
    traceback.print_list(stack_trace)

def ok (msg):
    print(f"{bcolors.OKGREEN}{msg}{bcolors.ENDC}")

def error (msg, fail=1):
    print(f"{bcolors.FAIL}{msg}{bcolors.ENDC}")
    if fail:
        sys.exit(1)
    stack_trace = traceback.extract_tb(sys.exc_info()[2])
    # Print the modified stack trace
    traceback.print_list(stack_trace)

def dier (msg):
    pprint(msg)
    sys.exit(1)

def count_events_on_date(date):
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    query = f'''
        SELECT COUNT(*)
        FROM events
        WHERE
        DATE(DATETIME(dt, 'unixepoch')) = '{date}'
    '''

    debug(query)
    c.execute(query)
    
    result = c.fetchone()
    conn.close()
    return result[0]

import curses
import datetime
import sys
import termios
import tty
import holidays
import locale

locale.setlocale(locale.LC_TIME, 'de_DE.UTF-8')

def choose_date(year, month):
    # Save the original terminal settings

    # Initialize curses
    stdscr = curses.initscr()
    curses.cbreak()
    curses.noecho()
    stdscr.keypad(True)
    curses.start_color()
    curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)

    # Define some constants for layout
    HEADER_HEIGHT = 3
    CELL_WIDTH = 4

    # Define some helper functions
    def get_month_days(year, month):
        return datetime.date(year, month, 1).strftime("%B %Y")

    def draw_header():
        month_days = get_month_days(year, month)
        header_text = f" {month_days} "
        stdscr.addstr(0, 0, header_text.center(curses.COLS))

    def draw_calendar():
        # Get the days of the month as a list of date objects
        days = []
        for day in range(1, 32):
            try:
                date = datetime.date(year, month, day)
                days.append(date)
            except ValueError:
                break

        # Calculate the starting day of the month
        weekday = days[0].weekday()

        # Define holidays
        saxon_holidays = holidays.CountryHoliday('DE', state='SN', years=[year])

        curses.initscr()

        # Draw the calendar
        for i, day in enumerate(days):
            row = i // 7 + HEADER_HEIGHT
            col = (i % 7) * CELL_WIDTH
            style = curses.A_REVERSE if day == chosen_date else 0
            if day.weekday() >= 5:  # weekend
                style |= curses.color_pair(1)  # red
            if day in saxon_holidays:  # holiday
                style |= curses.A_ITALIC
                holiday_name = saxon_holidays[day]
                stdscr.addstr(curses.LINES-1, col, str(day.day).center(CELL_WIDTH), style)
                stdscr.addstr(curses.LINES-1, col+1, holiday_name.center(CELL_WIDTH), style)
            stdscr.addstr(row, col, str(day.day).center(CELL_WIDTH), style)


    # Initialize the chosen date to the current day
    chosen_date = datetime.date.today()

    # Enter the main loop
    while True:
        # Clear the screen
        stdscr.clear()

        # Draw the header and calendar
        draw_header()
        draw_calendar()

        # Refresh the screen
        stdscr.refresh()

        # Get a keystroke from the user
        key = stdscr.getch()

        # Handle the keystroke
        if key == curses.KEY_LEFT:
            chosen_date -= datetime.timedelta(days=1)
            if chosen_date.month != month:
                month = chosen_date.month
                year = chosen_date.year
        elif key == curses.KEY_RIGHT:
            chosen_date += datetime.timedelta(days=1)
            if chosen_date.month != month:
                month = chosen_date.month
                year = chosen_date.year
        elif key == curses.KEY_UP:
            chosen_date -= datetime.timedelta(days=7)
        elif key == curses.KEY_DOWN:
            chosen_date += datetime.timedelta(days=7)
        elif key == ord('\n'):
            # Restore the original terminal settings before exiting
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, orig_settings)
            curses.nocbreak()
            stdscr.keypad(False)
            curses.echo()
            curses.endwin()
            return chosen_date

    # Clean up curses before exiting
    curses.nocbreak()
    stdscr.keypad(False)
    curses.echo()
    curses.endwin()
    # Restore the original terminal settings before exiting
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, orig_settings)


def days_until(date_str):
    """
    Calculates the number of days until the given date.
    Date should be in the format YYYY-MM-DD.
    """
    try:
        year, month, day = [int(x) for x in date_str.split('-')]
        target_date = datetime.date(year, month, day)
        today = datetime.date.today()
        delta = target_date - today
        if delta.days > 0:
            return f"{delta.days}"
        elif delta.days == 0:
            return "0"
        else:
            return f"{abs(delta.days)} days since {target_date.strftime('%Y-%m-%d')}"
    except ValueError:
        return "Invalid date format. Please use YYYY-MM-DD."


def is_weekend(day, month, year):
    # Create a datetime object for the given date
    date_obj = datetime.datetime(year, month, day)

    # Check if the date falls on a weekend
    return date_obj.weekday() >= 5


def prepare (msg):
    pattern = r"\s+(\d*):\s*$"

    # Define the replacement string
    replacement = r" \1:00:00"

    output_string = re.sub(pattern, replacement, msg)

    return output_string



def get_day_of_week(year, month, day):
    # Create a datetime object for the given date
    date_obj = datetime.datetime(year, month, day)

    # Use the strftime() method to format the date as a string
    # with the weekday name (e.g., "Monday", "Tuesday", etc.)
    day_of_week = date_obj.strftime('%A')

    return day_of_week

def print_calendar(year, month, blinking_dates=[], red_marked_days=[]):
    """
    Displays a calendar for a given year and month, highlighting the dates specified in the blinking_dates array.
    """

    de_holidays = holidays.DE(years=year, prov="SN")
    saxony_holidays_this_month = [date for date in de_holidays if date.month == month]

    current_time = datetime.datetime.now()

    current_year = datetime.datetime.now().year
    current_month = datetime.datetime.now().month
    current_day = datetime.datetime.now().day

    formatted_time = current_time.strftime(f"Now is {bcolors.RED}%Y-%m-%d %H:%M:%S{bcolors.ENDC}")
    print(formatted_time)

    # Set the first day of the week to Sunday
    calendar.setfirstweekday(calendar.MONDAY)

    # Get the calendar for the specified month and year
    cal = calendar.monthcalendar(year, month)

    # Print the calendar header
    month_name = calendar.month_name[month]

    width = 5  # example width
    spaces = " " * width

    print(f"{bcolors.BOLD}{month_name} {year}{bcolors.ENDC}")

    print(f"{bcolors.UNDERLINE}{bcolors.OKBLUE}Mo{spaces}Tu{spaces}We{spaces}Th{spaces}Fr{spaces}{bcolors.OKGREEN}Sa{spaces}Su{bcolors.ENDC}")

    future_holidays = []

    # Print each week of the calendar, highlighting the marked dates
    real_day = 0
    for week in cal:
        week_str = ''
        for day in week:
            real_day = real_day + 1
            day_str = ""

            holidays_green = [date.day for date in saxony_holidays_this_month]

            if day in red_marked_days:
                day_str = f"{bcolors.RED}{day:0>2}{bcolors.ENDC}"
            else:
                day_str = f"{day:0>2}"


            if day_str == "00":
                day_str = ""

            if real_day in holidays_green:
                day_str = f"{bcolors.ONGREEN}{day_str}{bcolors.ENDC}"

            if real_day in [date.day for date in saxony_holidays_this_month]:
                day_str = f"{bcolors.OKGREEN}{day_str}{bcolors.ENDC}"
                future_holidays.append([date for date in saxony_holidays_this_month if date.day >= real_day][0])

            else:
                is_we = False
                try:
                    is_we = is_weekend(real_day, month, year)
                except:
                    pass


                if is_we:
                    day_str = f"{bcolors.OKGREEN}{day_str}{bcolors.ENDC}"

                if real_day in blinking_dates:
                    day_str = f"{bcolors.BLINK}{day_str}{bcolors.ENDC}"

                if year == current_year and month == current_month and current_day == real_day:
                    day_str = f"{bcolors.UNDERLINE}{day_str}{bcolors.ENDC}"

            if day_str:
                ds = f"{year}-{month:0>2}-{day:0>2}"
                count = count_events_on_date(ds)

                # if there are no events, set the count to an empty string
                if count == 0:
                    count_str = spaces

                # center the count within the given width, with spaces on either side
                count_str = str(count) if count <= 99 else "99+"
                count_str = f"({count_str})"
                if count == 0:
                    count_str = " " * len(count_str)
                count_str = count_str.center(width)

                day_str = f"{day_str}{count_str}"


            week_str += day_str
        print(week_str)

    de_holidays = holidays.DE(years=year, prov="SN")
    if len(future_holidays) >= 0:
        print(f"{bcolors.OKGREEN}Anstehende Feiertage:{bcolors.ENDC}")
        for holiday in future_holidays:
            holiday_name = de_holidays.get(holiday)
            du = days_until(str(holiday))
            print(str(holiday) + ": " + holiday_name + ", days until: " + str(du))

def properly_formatted_datetime (date_string):
    if not date_string:
        return None
    # If time is not present in the date string, add default time 00:00:00
    try:
        if len(date_string) == 10:
            date_string += " 00:00:00"

        # Convert the string to datetime object
        date = datetime.datetime.strptime(date_string, '%Y-%m-%d %H:%M')

        # Format the date with zero-filled minutes and seconds
        formatted_date = date.strftime('%Y-%m-%d %H:%M:%S')
        return formatted_date
    except Exception as e:
        debug(e)
        pass

    return date_string

def convert_date_string(date_string):
    # Set the locale to German, assuming that the input string is in German format
    locale.setlocale(locale.LC_TIME, 'de_DE')

    # Parse the date string using datetime.strptime
    dt = datetime.datetime.strptime(date_string, '%A, %d. %B %Y %H:%M')

    # Format the datetime object as a string in the desired format
    res = dt.strftime('%Y-%m-%d %H:%M:%S')

    res = re.sub(r":(\d+):\d+", r":\1", res)

    return res

def parse_input (msg):
    msg = prepare(msg)

    name = None
    date = None

    # 0 = Einmaliges Ereignis
    # 1 = Jede Woche
    # 2 = Jede zweite Woche

    each = 0

    # Define the regular expression pattern
    split_by_pattern = r"^\s*(.*)\s*:\s(.*?)\s*$"

    # Use the re.match() function to match the pattern to the input string
    match = re.match(split_by_pattern, msg)

    date = None
    err = ""
    d = None
    each_word = None

    if match:
        # Extract the first and second substrings using the groups() method of the match object
        first_substring = match.group(1)
        second_substring = match.group(2)

        # Print the substrings
        date = first_substring
        name = second_substring


    if not name or not date:
        err = f"The line could not be parsed properly:\n{msg}"
    else:
        # tuesday at 12:15:00
        each_pattern = r'\s*(?:^|(?:(each|this|every))?\s+(?:(\d+?)[rsthnd]*?)?)?\s+(.*?day.*?)$'
        each_match = re.search(each_pattern, date)

        parse_date_part = date

        if each_match:
            parse_date_part = each_match.groups(3)[2]
            each_or_this = each_match.groups(1)[0]
            each_word = each_or_this
            if each_or_this == "this":
                each = 0
            else:
                try:
                    each = int(each_match.groups(2)[1])
                except:
                    debug("Couldnt be converted into integer: " + str(each_match.groups(2)[1]) + ", setting each to 1")
                    each = 1
        else:
            parse_date_part = date



        try:
            new_date_string = convert_date_string(parse_date_part)
            parse_date_part = properly_formatted_datetime(parse_date_part)
            if new_date_string:
                parse_date_part = f"{new_date_string}: {name}"
        except:
            pass

        try:
            try:
                start_time_obj = datetime.datetime.strptime(parse_date_part, "%Y-%m-%d %H:%M:%S")
                d = start_time_obj.timestamp()
            except ValueError:
                try:
                    start_time_obj = datetime.datetime.strptime(parse_date_part + ":00", "%Y-%m-%d %H:%M:%S")
                    d = start_time_obj.timestamp()
                except Exception as e:
                    try:
                        d = timefhuman(parse_date_part)
                    except:
                        d = None
                        debug("not parsable: " + str(msg))
                        err = "Not parsable"
                        name = name,
                        each = 0
                        each_word = None
        except Exception as e:
            debug("parse_date_part: " + parse_date_part)
            err = str(e)
            error(e, 0)
            traceback.print_exc()

    if type(d) == datetime.datetime:
        d = d.timestamp()

    ret = {
        'date': d,
        'err': err,
        'name': name,
        'each': each,
        'each_word': each_word
    }

    debug(ret)

    return ret

#print(parse_input("each 2nd tuesday at 12:15:00: hallo"))

def format_time(start_time):
    # Convert the start_time string to a datetime object
    try:
        start_time_obj = datetime.datetime.strptime(start_time, "%H:%M:%S")
    except ValueError:
        try:
            start_time_obj = datetime.datetime.strptime(start_time, "%H:%M")
        except ValueError:
            try:
                start_time_obj = datetime.datetime.strptime(start_time, "%H")
            except ValueError:
                return False

    # Convert the datetime object back to a string with the desired format
    formatted_time = start_time_obj.strftime("%H:%M:%S")

    # Return the formatted string
    return formatted_time

def confirm_action(question):
    """
    Asks the user whether an action should be confirmed or not,
    returning True if the user confirms and False if the user does not confirm.
    """
    # Remove everything that is not y/n/Y/N from the input
    valid_choices = ['y', 'n']
    user_input = read_input_without_history(f"{question} (Y/n)? ")
    if not user_input:
        user_input = "y"
    user_input = user_input.lower()
    user_input = ''.join(filter(lambda c: c in valid_choices, user_input))

    # If the user enters "y" or presses enter, return True
    if user_input.startswith('y') or user_input == "":
        return True
    # If the user enters "n", return False
    elif user_input.startswith('n'):
        return False
    # If the user enters something else, ask again
    else:
        print("Invalid choice. Please enter y/n.")
        return confirm_action(question)

def print_overview (current_year = datetime.datetime.now().year, current_month = datetime.datetime.now().month, current_day = datetime.datetime.now().day):
    red_marked_days = get_event_dates(int(current_year), current_month)
    print_calendar(current_year, current_month, [], red_marked_days)

    print_events_on_date(current_year, current_month, current_day)

def msgbox (title, msg):
    easygui.msgbox(msg, title=title)


def delete_event(event_id):
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    
    c.execute('SELECT dt, description FROM events WHERE id = ?', (event_id,))
    result = c.fetchone()
    if result:
        dt = datetime.datetime.fromtimestamp(result[0]).strftime('%Y-%m-%d %H:%M')
        description = result[1]
        
        c.execute('DELETE FROM events WHERE id = ?', (event_id,))
        conn.commit()
        conn.close()
        ok(f"Deleted event. Can be re-inserted by: {dt}: {description}")
    else:
        conn.close()
        error(f"Event not found: {event_id}", 0)

def _help ():
    print("Example inputs:")
    print("")
    print("upcoming Monday noon: event xyz")
    print("next friday at 13:30: event abc")
    print("in 5 minutes: https://google.de")
    print("every 2nd week at wednesday: meeting")
    print("03-02-2022 12:00: test-event")
    print("dd-mm-yyyy hh:mm: test event")
    print("")
    print("list")
    print("help")
    print("rm 1,2,3 # (event ids)")
    print("")

def handle_hours_minutes(user_input):
    # Define the regular expression
    regex = r'^(?:\+|in)\s*(\d+)\s*h(?:ours?)?\s*(?:and|:)?\s*(\d+)\s*min(utes?)?:\s*(.*)'

    # Match the regular expression
    match = re.match(regex, user_input)

    skip = False

    if match:
        # Extract the number of hours and minutes from the match
        hours = int(match.group(1))
        minutes = int(match.group(2))

        # Calculate the datetime for the specified time
        now = datetime.datetime.now()
        target_time = now + datetime.timedelta(hours=hours, minutes=minutes)

        # Convert the target time to the requested format
        formatted_time = target_time.strftime("%Y-%m-%d %H:%M:%S")

        skip = True

        return f"{formatted_time}: {match.group(3)}"

    return user_input

def handle_hours(user_input):
    # Define the regular expression
    # in 48h: test
    regex = r'^(?:\s*(?:in|\+)\s*(\d+)\s*(?:h[ours]*)\s*:)\s*(.*)'

    # Match the regular expression
    match = re.match(regex, user_input)
    skip = False

    if match:
        # Extract the number of minutes from the match
        hours = int(match.group(1))

        # Calculate the datetime for the specified time
        now = datetime.datetime.now()
        target_time = now + datetime.timedelta(hours=hours)

        # Convert the target time to the requested format
        formatted_time = target_time.strftime("%Y-%m-%d %H:%M:%S")

        skip = True

        return f"{formatted_time}: {match.group(2)}"

    return user_input


def handle_minutes(user_input):
    # Define the regular expression
    regex = r'^in\s*(\d+)\s*(?:m[inutes]+)?:\s*(.*)'

    # Match the regular expression
    match = re.match(regex, user_input)

    skip = False

    if match:
        # Extract the number of minutes from the match
        minutes = int(match.group(1))

        # Calculate the datetime for the specified time
        now = datetime.datetime.now()
        target_time = now + datetime.timedelta(minutes=minutes)

        # Convert the target time to the requested format
        formatted_time = target_time.strftime("%Y-%m-%d %H:%M:%S")

        skip = True

        return f"{formatted_time}: {match.group(2)}"

    return user_input

def handle_rm (user_input):
    skip = False
    delete_pattern = re.compile(r'^(?:delete|rm)\s*([\d,\s]+)$')  # Updated regex pattern to match multiple event ids separated by commas and spaces
    match = delete_pattern.match(user_input)
    if match:
        event_ids = [int(id.strip() or -1) for id in match.group(1).split(',')]  # Extract event ids from matched groups and convert them to integers
        for event_id in event_ids:
            if event_id != -1:
                delete_event(event_id)
        skip = True

    list_pattern = re.compile(r'^list\s+(\d{1,2})(?:-(\d{1,2})?(?:-(\d{4}))?)$')
    match = list_pattern.match(user_input)
    if match:
        if match.group(1):
            # Extract the date string from the command and parse it into a datetime object
            try:
                day = match.group(3)
                month = match.group(2)
                year = match.group(1)

                print_overview(day, month, year)
            except Exception as e:
                debug(e)
            skip = True


    return skip

from dateutil.parser import parse
from dateutil.relativedelta import relativedelta

def handle_cronlike (msg):
    match = re.match(r"every (\b\w+\b) at (\d{1,2})(?::(\d{2})):\s+(.*)\s*", msg)

    if match:
        crontab_str = human_to_crontab(msg)
        new_id = insert_crontab(crontab_str, match.group(4))

        if new_id:
            ok("Task created")
        else:
            warning("Something seems to have gone wrong. No ID")

def handle_list_command(user_input):
    today = datetime.date.today()

    match = re.match(r"list\s*(\d{4})-(\d{1,2})-(\d{1,2})", user_input)

    if match:
        year = int(match.group(3))
        month = int(match.group(2))
        day = int(match.group(1))

        print_overview(day, month, year)
    else:
        warning("Date-Regex doesnt match")

def parse_line (user_input):
    skip = False
    edit = False

    if user_input == "chose" or user_input == "choose":
        current_year = datetime.datetime.now().year
        current_month  = datetime.datetime.now().month

        date = choose_date(current_year, current_month)
        if not date:
            skip = True
        else:

            start_time = read_input_without_history("Starting time: ")
            if start_time:
                print(f"Start-time: {start_time}")
                start_time = format_time(start_time)
                msg = read_input_without_history("Message: ")

                try:
                    date = date.strftime('%Y-%m-%d')
                    debug("date:" + str(date))
                    user_input = f"{date} {start_time}: {msg}"
                except Exception as e:
                    user_input = f"YY-MM-DD HH:MM: {msg}"
                    debug(e)
                    edit = True
                    pass


                debug(user_input)
            else:
                print("")
                skip = True

    if user_input == "exit" or user_input == "quit" or user_input == "q":
        debug(f"Exiting, because I received the command {user_input}")
        sys.exit(0)

    if user_input == "stat":
        try:
            plot_event_statistics()
        except Exception as e:
            error(e, 0)
        skip = True

    if user_input == "debug":
        args.debug = not args.debug
        skip = True

    if user_input == "test":
        user_input = "each 3nd friday at 12:15:00: hallo"
    if user_input == "calendar" or user_input == "cal":
        print_overview()
        skip = True

    if user_input == "clear":
        skip = True
        os.system('clear')
    if user_input == "list":
        print_overview()
        skip = True

    if not skip:
        # Define a regular expression pattern to match the desired pattern
        pattern = r"(?:ScaDS\.AI\s*Chat\s*Bot:)\s*remind\ssingle\s*(\d{4}-\d{2}-\d{2}\s*\d{1,2}(?::\d{1,2}(?::\d{1,2})?)?)\s+(.*)"

        # Use the re module to search for the pattern in the text
        match = re.search(pattern, user_input)

        # If the pattern is found, extract the date and message and format them as desired
        if match:
            date = match.group(1)
            message = match.group(2)
            user_input = f"{date}: {message}"
            debug("user_input: " + str(user_input))


    if not skip:
        list_match = re.match(r"list\s*(\d{4})-(\d{1,2})-(\d{1,2})", user_input)

        if list_match:
            try:
                handle_list_command(user_input)
            except Exception as e:
                debug(e)
            skip = True

    if user_input == "help":
        _help()
        skip = True
    if not user_input.strip():
        skip = True

    if not skip:
        match = re.match(r"every (\b\w+\b) at (\d{1,2})(?::(\d{2}))", user_input)

        if match:
            try:
                handle_cronlike(user_input)
            except Exception as e:
                error(e, 0)

            skip = True

    if not skip:
        skip = handle_rm(user_input)

    if not skip:
        user_input = handle_minutes(user_input)

    if not skip:
        user_input = handle_hours(user_input)

    if not skip:
        user_input = handle_hours_minutes(user_input)

    if not skip:
        new_date_year = None
        new_date_month = None

        try:
            parse_result = parse_input(user_input)
            if parse_result["err"] and edit == False:
                error(parse_result["err"], 0)
            else:
                edit = True

                if not edit:
                    marked_dates_1 = []
                    red_marked_days = []
                    try:
                        red_marked_days = []
                        blinking_dates = []

                        try:
                            new_date_year = parse_result["date"].year
                            new_date_month = parse_result["date"].month
                            new_date_day = parse_result["date"].day
                            blinking_dates = [new_date_day]

                            if current_year == new_date_year and current_month == new_date_month:
                                red_marked_days = [current_day]
                            red_marked_days = get_event_dates(int(new_date_year), new_date_month)
                        except Exception as e:
                            debug(e)
                            edit = True
                            pass

                        print_calendar(new_date_year, new_date_month, blinking_dates, red_marked_days)
                    except Exception as e:
                        debug(e)
                        edit = True
                        pass



                    if not parse_result["date"] or not parse_result["name"]:
                        edit = True
                    else:
                        try:
                            try:
                                print_events_on_date(parse_result["date"].year, parse_result["date"].month, parse_result["date"].day)
                            except:
                                pass
                            edit = not confirm_action("Detected the date " + str(parse_result["date"]) + " and the event name '" + str(parse_result["name"]) + "'. Is that correct")
                        except Exception as e:
                            debug(e)
                            pass

                    if edit:
                        try:
                            # Use readline to get user input
                            readline.set_startup_hook(lambda: readline.insert_text(user_input))
                            readline.set_startup_hook()
                        except ValueError as e:
                            # Print error message and allow user to edit input
                            print(f'Error: {e}')
                if not parse_result["err"]:
                    if parse_result["date"]:
                        dt = datetime.datetime.utcfromtimestamp(parse_result["date"])

                        new_date_year = dt.year
                        new_date_month = dt.month
                        new_date_day = dt.day

                        dts = int(parse_result["date"])
                        n = parse_result["name"]
                        each = 0

                        try:
                            each = parse_result["each"]
                        except Exception as e:
                            each = 0

                        debug("User-input: " + str(user_input))
                        new_event_id = insert_event(dts, n, each)

                        if new_event_id:
                            if new_date_month:
                                if new_date_year:
                                    red_marked_days = get_event_dates(int(new_date_year), new_date_month)
                                    blinking_dates = []
                                    if new_date_day:
                                        blinking_dates = [new_date_day]

                                    debug("blinking_dates:")
                                    debug(blinking_dates)

                                    print_calendar(new_date_year, new_date_month, blinking_dates, red_marked_days)

                                    return True
                                else:
                                    debug("No new_date_year defined")
                            else:
                                debug("No new_date_month defined")
                    else:
                        warning(f"Date could not be parsed from '{user_input}'")
                else:
                    error(parse_result["err"], 0)
        except Exception as e:
            warning(e)
    if skip:
        return True
    return False

def input_shell():
    # Set up readline to allow for tab completion and history
    print_overview()
    readline.set_history_length(100)

    _help()

    # Continuously prompt the user for input
    while True:
        current_year = datetime.datetime.now().year
        current_month = datetime.datetime.now().month
        current_day = datetime.datetime.now().day

        # Get user input and add it to history
        try:
            user_input = input(">> ")
        except EOFError as e:
            sys.exit(0)
        except KeyboardInterrupt as e:
            sys.exit(0)

        # Get the last element of the history list
        last_command = readline.get_history_item(readline.get_current_history_length() - 1)

        if "Deleted event. Can be re-inserted by: " in user_input:
            user_input = user_input.replace("Deleted event. Can be re-inserted by: ", "")

        res = parse_line(user_input)

        #if not res:
        #    error("Last command failed: " + str(user_input), 0)

        # Check if the current command is the same as the last command
        if last_command and last_command.strip() == user_input.strip():
            # Do not add the current command to the history
            # readline.remove_history_item(readline.get_current_history_length() - 1)
            pass
        else:
            # Add the current command to the history
            readline.add_history(user_input)

import sqlite3
import pandas as pd
import matplotlib.pyplot as plt

def plot_event_statistics():
    # Connect to the database
    conn = sqlite3.connect(db_file)
    c = conn.cursor()

    # Retrieve the data from the events table
    query = "SELECT DATE(DATETIME(dt, 'unixepoch')) as date, weeks_multiplier, has_been_shown, COUNT(*) AS count FROM events GROUP BY dt"
    df = pd.read_sql_query(query, conn)
    df['date'] = pd.to_datetime(df['date'])

    # Create a figure with three subplots
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(15, 5))

    # Create a bar chart of the number of events shown vs. not shown
    shown_count = df['has_been_shown'].sum()
    not_shown_count = len(df) - shown_count
    ax1.bar(['Shown', 'Not Shown'], [shown_count, not_shown_count])
    ax1.set_xlabel('Event Status')
    ax1.set_ylabel('Number of Events')
    ax1.set_title('Events Shown vs. Not Shown')

    # Create a line plot of the number of events grouped by day
    events_by_day = df.groupby('date').count()
    ax2.plot(events_by_day.index, events_by_day)
    ax2.set_xlabel('Date')
    ax2.set_ylabel('Number of Events')
    ax2.set_title('Events Grouped by Day')

    # Create a line plot of the average number of events per month over time
    events_by_month = df.groupby(pd.Grouper(key='date', freq='M')).count()
    events_by_month['count'].plot(ax=ax3)
    ax3.set_xlabel('Date')
    ax3.set_ylabel('Average Number of Events per Month')
    ax3.set_title('Average Number of Events per Month over Time')

    # Show the plot
    plt.show()

    # Close the database connection
    conn.close()


def save_history():
    readline.write_history_file(history_file)
    # Clean up curses before exiting
    curses.initscr()
    curses.nocbreak()
    curses.echo()
    curses.endwin()
    # Restore the original terminal settings before exiting
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, orig_settings)

import atexit
atexit.register(save_history)

if args.headless:
    while True:
        now = datetime.datetime.now()
        formatted_time = now.strftime("%A, %B %d, %Y %I:%M:%S %p")
        print(f'{formatted_time}: Checking events')
        initialize_table()
        show_upcoming_events_with_gui()
        time.sleep(1)
else:
    # Start the GUI
    input_shell()
