#!/usr/bin/env python3
"""
 Calculates growth and trends for unique page counts from Analytics Data API v1 (newer GA4 model)

 Starting point attribution:
 https://developers.google.com/analytics/devguides/reporting/data/v1/quickstart-client-libraries
"""

#
# from inside venv:
# pip3 install google-analytics-data
# pip3 install --upgrade oauth2client
# pip3 freeze | tee requirements.txt
#
import sys
import traceback
import argparse

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    OrderBy,
    RunReportRequest,
)


from google.oauth2 import service_account

def initialize_ga4_analyticsreporting(jsonKeyFilePath):
  """Initializes an Analytics Reporting API V4 service object.
  https://googleapis.dev/python/google-api-core/latest/auth.html

  Returns:
    An authorized Analytics Data API v1 service object.
  """
  credentials = service_account.Credentials.from_service_account_file(jsonKeyFilePath)

  # Scope already defaults to 'analytics.readonly'
  # https://googleapis.dev/dotnet/Google.Analytics.Data.V1Beta/1.0.0-beta01/api/Google.Analytics.Data.V1Beta.BetaAnalyticsDataClient.html
  #SCOPES = ['https://www.googleapis.com/auth/analytics.readonly']

  # Build the service object. 
  client = BetaAnalyticsDataClient(credentials=credentials)
  return client


def get_unique_pagecount_report(client,property_id,startDateStr,endDateStr):
    """Runs a report on a Google Analytics GA4 property."""

    request = RunReportRequest(
        property=f"properties/{property_id}",
        dimensions=[Dimension(name="pagePath")],
        metrics=[Metric(name="activeUsers")],
        date_ranges=[DateRange(start_date=startDateStr, end_date=endDateStr)],
        order_bys=[ OrderBy(metric = {'metric_name': 'activeUsers'}, desc = False) ]
    )
    response = client.run_report(request)
    return response

def build_pagecount_dict(response):
  """Parses and prints the Analytics Data API v1 response.
  """
  result = {}
 
  for row in response.rows:
    pageCount=row.metric_values[0].value
    path=row.dimension_values[0].value
    #print(f"{pageCount},{path}")
    valid_path = not(
      "?" in path or  
      "&" in path or  
      "/category/" in path or  
      "/page/" in path or  
      "/tag/" in path or
      len(path) < 16 # eliminates spam requests and ones pointing to just dates
      )
    if valid_path:
      result[path] = pageCount
      #print(f"{pageCount},{path}")

  return result

def main():

  examples = '''USAGE:
 jsonKeyFile googleGA4PropertyID [reportingDays=30]

 jsonKeyFile is the Google service account json key file
 googleGA4PropertyID can be seen by going to Google Analytics, Admin>Property Settings
 reportingDays is the number of days to rollup into reporting block (today-reportingDays)


 EXAMPLES:
 my.json 123456789
 my.json 123456789 14
'''

  # define arguments
  ap = argparse.ArgumentParser(description="Calculate growth/trends from Analytics",epilog=examples,formatter_class=argparse.RawDescriptionHelpFormatter)
  ap.add_argument('key', help="json key of Google service account")
  ap.add_argument('propertyId', help="GA4 propertyID from Google Analytics (Admin>Property Settings)")
  ap.add_argument('-d', '--days', default="30",help="number of days in reporting window")
  args = ap.parse_args()

  print(f"service account json={args.key}, Google Analytics propertyID={args.propertyId}, reporting window={args.days} days")
  client = initialize_ga4_analyticsreporting(args.key)

  #sample_run_report(client,args.propertyId)
  
  # get unique page counts per reporting day width
  ndays=int(args.days)
  response_latest = get_unique_pagecount_report(client, args.propertyId, startDateStr=f"{ndays}daysAgo", endDateStr="0daysAgo")
  response_older  = get_unique_pagecount_report(client, args.propertyId, startDateStr=f"{ndays*2}daysAgo", endDateStr=f"{ndays+1}daysAgo")
  print(f"lastest reporting window: 0daysAgo -> {ndays}daysAgo")
  print(f"older   reporting window: {ndays+1}daysAgo -> {ndays*2}daysAgo")
  print()

  #print_pagecount_response_csv(response_latest)
  #print_pagecount_response_csv(response_older)

  # build dictionary of page->count
  pagecounts_latest = build_pagecount_dict(response_latest)
  pagecounts_older  = build_pagecount_dict(response_older)

  # build dictionary for page->delta count, page->delta percent
  pagecounts_delta = {}
  pagecounts_delta_percent = {}
  for path in pagecounts_latest:
    try:
      count_latest = pagecounts_latest[path]
      if path in pagecounts_older:
        count_older  = pagecounts_older[path]

        # calculate absolute difference between timeframes
        delta = int(count_latest) - int(count_older)
        # calculate percent change in terms of total count
        delta_percent = float(delta)/float(count_latest)

        # save results
        pagecounts_delta[path] = int(delta)
        pagecounts_delta_percent[path] = float(delta_percent)
        #print(f"{count_latest},{count_older},{delta},{delta_percent},{path}")
      else:
        #print(f"OLDERKEYMISSING does not exist {path} newer count was {count_latest}")
        pass
    except KeyError:
      print(f"KEYERROR {path}")
      traceback.print_exc()

  # sort absolute deltas and percent so we can see trends
  # array of tuples
  sorted_deltas = sorted(pagecounts_delta.items(), key=lambda x:x[1])
  sorted_deltas_percent = sorted(pagecounts_delta_percent.items(), key=lambda x:x[1])
  #for row in sorted_deltas:
  #  print(f"{row[1]},{row[0]}")

  # how many losers/winners to display
  nrows=25

  # show losers and winners in terms of absolute hits
  print("====BIGGEST LOSERS======")
  print("delta,count,path")
  for row in sorted_deltas[:nrows]:
    delta=row[1]
    path=row[0]
    totalcount=pagecounts_latest[path]
    print(f"{delta},{totalcount},{path}")

  print("====BIGGEST WINNERS======")
  print("delta,count,path")
  for row in sorted_deltas[-nrows:]:
    delta=row[1]
    path=row[0]
    totalcount=pagecounts_latest[path]
    print(f"{delta},{totalcount},{path}")

  # show losers and winners in terms of percent growth (% of total)
  print("====TRENDING DOWN======")
  print("growth%,newcount,oldcount,path")
  for row in sorted_deltas_percent[:nrows]:
    percent=row[1]
    path=row[0]
    totalcount=pagecounts_latest[path]
    oldcount=pagecounts_older[path]
    print(f"{percent*100:.0f}%,{totalcount},{oldcount},{path}")

  print("====TRENDING UP======")
  print("growth%,newcount,oldcount,path")
  for row in sorted_deltas_percent[-nrows:]:
    percent=row[1]
    path=row[0]
    totalcount=pagecounts_latest[path]
    oldcount=pagecounts_older[path]
    print(f"{percent*100:.0f}%,{totalcount},{oldcount},{path}")

if __name__ == '__main__':
  main()
