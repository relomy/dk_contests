"""
Find contests for a sport and print cron job.

URL: https://www.draftkings.com/lobby/getcontests?sport=NBA
Response format: {
    'SelectedSport': 4,
    # To find the correct contests, see: find_new_contests()
    'Contests': [{
        'id': '16911618',                              # Contest id
        'n': 'NBA $375K Tipoff Special [$50K to 1st]', # Contest name
        'po': 375000,                                  # Total payout
        'm': 143750,                                   # Max entries
        'a': 3.0,                                      # Entry fee
        'sd': '/Date(1449619200000)/'                  # Start date
        'dg': 8014                                     # Draft group
        ... (the rest is unimportant)
    },
    ...
    ],
    # Draft groups are for querying salaries, see: run()
    'DraftGroups': [{
        'DraftGroupId': 8014,
        'ContestTypeId': 5,
        'StartDate': '2015-12-09T00:00:00.0000000Z',
        'StartDateEst': '2015-12-08T19:00:00.0000000',
        'Sport': 'NBA',
        'GameCount': 6,
        'ContestStartTimeSuffix': null,
        'ContestStartTimeType': 0,
        'Games': null
    },
    ...
    ],
    ... (the rest is unimportant)
}
"""

import argparse
import datetime
import re
from collections import defaultdict

import browsercookie
import requests
from pytz import timezone


class Contest(object):
    def __init__(self, contest):
        self.contest = contest
        self.startDate = contest["sd"]
        self.name = contest["n"]
        self.id = contest["id"]
        self.draftGroup = contest["dg"]
        self.totalPrizes = contest["po"]
        self.entries = contest["m"]
        self.entryFee = contest["a"]
        self.entryCount = contest["ec"]
        self.maxEntryCount = contest["mec"]
        self.attr = contest["attr"]
        self.isDoubleUp = False

        self.startDt = self.get_dt_from_timestamp(self.startDate)

        if "IsDoubleUp" in self.attr:
            self.isDoubleUp = self.attr["IsDoubleUp"]

    def get_dt_from_timestamp(self, timestamp_str):
        timestamp = float(re.findall(r"[^\d]*(\d+)[^\d]*", timestamp_str)[0])
        return datetime.datetime.fromtimestamp(timestamp / 1000)

    def __str__(self):
        print("name: {}".format(self.name))
        print("dateTime: {}".format(self.startDate))
        print("startDt: {}".format(self.startDt))
        print("contest id: {}".format(self.id))
        print("draft group: {}".format(self.draftGroup))
        print("totalPrizes: {}".format(self.totalPrizes))
        print("entries: {}".format(self.entries))
        print("entryFee: {}".format(self.entryFee))
        print("entryCount: {}".format(self.entryCount))
        print("mec: {}".format(self.maxEntryCount))
        print("")
        return ""


def get_largest_contest(contests, dt, entry_fee=25, query=None, exclude=None):
    print("get_largest_contest(contests, {})".format(entry_fee))
    print(type(contests))
    print("contests size: {}".format(len(contests)))
    ls = []
    stats = {}
    stats["date"] = defaultdict(int)
    stats["SE_DU"] = defaultdict(int)

    for c in contests:
        stats["date"][c.startDt.strftime("%Y-%m-%d")] += 1

        if c.startDt.date() == dt.date():  # check if the date is correct
            if c.maxEntryCount == 1:  # single entry only

                # keep track of single-entry double ups
                if c.isDoubleUp:
                    stats["SE_DU"][c.entryFee] += 1

                if c.entryFee == entry_fee:  # match the entry fee
                    # if exclude is in the name, skip it
                    if exclude:
                        if exclude in c.name:
                            continue

                    # if query is in the name, add it to the list
                    if query:
                        if query in c.name:
                            ls.append(c)
                    else:
                        ls.append(c)

    print(stats)

    print("number of contests meeting requirements: {}".format(len(ls)))
    # sort contests by # of entries
    sorted_list = sorted(ls, key=lambda x: x.entries, reverse=True)

    # if there is a sorted list, return the first element
    if sorted_list:
        print("sorted_list: {}".format(sorted_list[0]))
        return sorted_list[0]

    return None


def get_contests_by_entries(contests, entry_fee, limit):
    return sorted(
        [c for c in contests if c.entryFee == entry_fee and c.entries > limit],
        key=lambda x: x.entries,
        reverse=True,
    )


def print_cron_string(contest, sport):
    print(contest)
    py_str = (
        "cd /home/pi/Desktop/dk_salary_owner/ && /home/pi/.local/bin/pipenv run python"
    )
    dl_str = py_str + " download_DK_salary.py"
    get_str = py_str + " get_DFS_results.py"

    # set interval and length depending on sport
    if sport == "NBA":
        sport_length = 5
        dl_interval = "*/10"
        get_interval = "*/5"
    elif sport == "MLB":
        sport_length = 7
        dl_interval = "1-59/15"
        get_interval = "2-59/10"
    elif sport == "PGA":
        sport_length = 8
        dl_interval = "3-59/30"
        get_interval = "4-59/15"
    elif sport == "TEN":
        sport_length = 15
        dl_interval = "4-59/15"
        get_interval = "5-59/10"

    # add about how long the slate should be
    end_dt = contest.startDt + datetime.timedelta(hours=sport_length)
    print("end: {}".format(end_dt))

    # if dates are the same, we don't add days or hours
    if contest.startDt.date() == end_dt.date():
        print("dates are the same")
        hours = "{}-{}".format(contest.startDt.strftime("%H"), end_dt.strftime("%H"))
        days = "{}".format(contest.startDt.strftime("%d"))
    else:
        print("dates are not the same - that means end_dt extends into the next day")
        # don't double print 00s
        if end_dt.strftime("%H") == "00":
            hours = "{},{}-23".format(
                end_dt.strftime("%H"), contest.startDt.strftime("%H")
            )
        else:
            hours = "00-{},{}-23".format(
                end_dt.strftime("%H"), contest.startDt.strftime("%H")
            )
        days = "{}-{}".format(contest.startDt.strftime("%d"), end_dt.strftime("%d"))

    cron_str = "{0} {1} {2} *".format(hours, days, end_dt.strftime("%m"))

    print(
        "{0} {1} {2} -s {3} -dg {4} >> /home/pi/Desktop/{3}_results.log 2>&1".format(
            dl_interval, cron_str, dl_str, sport, contest.draftGroup
        )
    )
    print(
        "{0} {1} export DISPLAY=:0 && {2} -s {3} -i {4} >> /home/pi/Desktop/{3}_results.log 2>&1".format(
            get_interval, cron_str, get_str, sport, contest.id
        )
    )


def valid_date(date_string):
    """Check date argument to determine if it is a valid
    
    Arguments:
        date_string {string} -- date from argument
    
    Raises:
        argparse.ArgumentTypeError: 
    
    Returns:
        datetime.datetime -- YYYY-MM-DD format
    """
    try:
        return datetime.datetime.strptime(date_string, "%Y-%m-%d")
    except ValueError:
        msg = "Not a valid date: '{0}'.".format(date_string)
        raise argparse.ArgumentTypeError(msg)


def main():
    """"""
    # parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-s",
        "--sport",
        choices=["NBA", "NFL", "CFB", "GOLF", "NHL", "MLB", "TEN"],
        required=True,
        help="Type of contest (NBA, NFL, GOLF, CFB, NHL, MLB, or TEN)",
    )
    parser.add_argument("-l", "--live", action="store_true", help="Get live contests")
    parser.add_argument(
        "-e", "--entry", type=int, default=25, help="Entry fee (25 for $25)"
    )
    parser.add_argument("-q", "--query", help="Search contest name")
    parser.add_argument("-x", "--exclude", help="Exclude from search")
    parser.add_argument(
        "-d",
        "--date",
        help="The Start Date - format YYYY-MM-DD",
        default=datetime.datetime.today(),
        type=valid_date,
    )
    args = parser.parse_args()

    live = ""
    print(args)
    if args.live:
        live = "live"

    # set cookies based on Chrome session
    COOKIES = browsercookie.chrome()
    URL = "https://www.draftkings.com/lobby/get{0}contests?sport={1}".format(
        live, args.sport
    )
    print(URL)
    HEADERS = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, sdch",
        "Accept-Language": "en-US,en;q=0.8",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        # 'Cookie': os.environ['DK_AUTH_COOKIES'],
        "Host": "www.draftkings.com",
        "Pragma": "no-cache",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_5) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/48.0.2564.97 Safari/537.36"
        ),
        "X-Requested-With": "XMLHttpRequest",
    }

    response = requests.get(URL, headers=HEADERS, cookies=COOKIES).json()
    response_contests = {}
    contests = []
    if isinstance(response, list):
        print("response is a list")
        response_contests = response
    elif "Contests" in response:
        print("response is a dict")
        response_contests = response["Contests"]
    else:
        print("response isn't a dict or a list??? exiting")
        exit()

    # create list of Contest objects
    for c in response_contests:
        contests.append(Contest(c))
    # TODO add switch to categorize types/dates of contests returned
    # for example
    # contests size: 562
    # dates: 2018-07-13: 500
    #        2018-07-14:  62

    contest = get_largest_contest(
        contests, args.date, args.entry, args.query, args.exclude
    )

    # check if contest is empty
    if not contest:
        exit("No contests found.")

    print("contest type: {}".format(type(contest)))

    # change GOLF back to PGA
    if args.sport == "GOLF":
        args.sport = "PGA"

    # start_hour = start_dt.strftime('%H')
    print("start: {}".format(contest.startDt))

    print_cron_string(contest, args.sport)


if __name__ == "__main__":
    main()
