import csv
import requests
import json
import datetime
from airtable import Airtable
import airtable
from bs4 import BeautifulSoup
from scraper_api import ScraperAPIClient
import vonage

#vonage api configure
VONAGE_KEY = '58c9a92e'
VONAGE_SECRET = 'V0WXtHsGLOORYsoZ'

#scraperapi api configure
SCRAPER_API_KEY = '47c476a985a8b25b176987faf739e342'

#airtable api configure
AIRTABLE_BASE_ID = 'appEDQ2nw23MBNc2l' #testing 'appSP5zxawuS3JXNp'
AIRTABLE_API_KEY = 'keyKfTTSVsYkHuprf' #testing 'keyVohsEPrHmjlmfR'
AIRTABLE_BASE_NAME = 'Collections'
AIRTABLE_VIEW_NAME = 'api_view_do_not_change'

#opensea api configuration
OPENSEA_API_KEY = '8af8b508e0be4a69a72f7c71b022af79'

def send_error_notification():
	vonage_client = vonage.Client(key=VONAGE_KEY, secret=VONAGE_SECRET)
	sms = vonage.Sms(vonage_client)
	#configure error to my number notification
	responseData = sms.send_message(
		{
			"from": "DigitalOcean Dev",
			"to": "447838070787",
			"text": "An error has occurred",
		}
	)
	#print response
	if responseData["messages"][0]["status"] == "0":
		print("Message sent successfully.")
	else:
		print(f"Message failed with error: {responseData['messages'][0]['error-text']}")

def get_number_tokens_listed(collection_slug):
	scraper_client = ScraperAPIClient(SCRAPER_API_KEY)
	#build query url
	result = scraper_client.get(url = 'https://opensea.io/collection/' + collection_slug + '?search[sortAscending]=true&search[sortBy]=PRICE&search[toggles][0]=BUY_NOW').text
	#parse raw html
	soup = BeautifulSoup(result.encode(),'html.parser')
	#find the number of results
	element = soup.select_one('div.AssetSearchView--results-count > span').text
	#filter non-numeric values
	numeric_filter = filter(str.isdigit, element)
	#join numeric values back together
	number_of_results = "".join(numeric_filter)
	return number_of_results

def calculate_percentage_tokens_listed(number_tokens_total, number_tokens_listed):
	quotient = int(number_tokens_listed) / int(number_tokens_total)
	percentage_tokens_listed = quotient * 100
	return percentage_tokens_listed

def write_price_to_csv(collection_slug, today, floor_price):
	# open the csv file in the write mode
	csv_file = open('opensea_prices.csv', 'a', newline='')
	# create the csv writer
	writer = csv.writer(csv_file)
	# create the row data
	row = [collection_slug,today.strftime("%Y-%m-%d"),floor_price]
	# append a row to the csv file
	writer.writerow(row)
	# close the file
	csv_file.close()

def get_price_ninety_days_ago(today, collection_slug):
	#create 90 days to subtract time delta
	ninety_days = datetime.timedelta(days = 90)
	#subtract ninety days from todays date to get the date of appropriate price
	unformated_date_ninety_days_ago = today - ninety_days
	#format the date
	date_ninety_days_ago = unformated_date_ninety_days_ago.strftime("%Y-%m-%d")
	#create null price to be overwritten if the csv has data from 90 days ago
	price_ninety_days_ago = 'None'
	#read csv
	with open('opensea_prices.csv', 'r') as csv_file:
		csv_data = csv.DictReader(csv_file)
		#loop through the csv list
		for row in csv_data:
			#if current rows first value is equal to the current collection and the date is appropriate
			if (row['collection_slug'] == collection_slug) and (row['price_date'] == str(date_ninety_days_ago)):
				#get the price
				price_ninety_days_ago = row['price']
	return price_ninety_days_ago

def calculate_ninety_day_price_change(floor_price, price_ninety_days_ago):
	#check not zero
	if float(floor_price) != 0 and float(price_ninety_days_ago) != 0:
		#calculate the 90 day price change
		ninety_day_price_change = float(floor_price) / float(price_ninety_days_ago) - 1
	else:
		ninety_day_price_change = 0
	return ninety_day_price_change

def update_collections():
	#airtable get base
	airtable = Airtable(AIRTABLE_BASE_ID, AIRTABLE_BASE_NAME, AIRTABLE_API_KEY)
	#base
	bases = airtable.get_iter(view=AIRTABLE_VIEW_NAME)
	#iterate through the base
	for base in bases:
		#incase of error
		try:
			#iterate through each row in the base
			for row in base:
				#get the id for the row in airtable
				id = row['id']
				#get the collection slug to query opensea api
				collection_slug = row['fields']['collection_slug']
				#create opensea query url
				opensea_url = "https://api.opensea.io/api/v1/collection/" + collection_slug
				#opensea headers
				headers = {"Accept": "application/json", "X-API-KEY": OPENSEA_API_KEY}
				#call the api
				response = requests.request("GET", opensea_url, headers=headers)
				#get datetime now for later in the script
				today = datetime.datetime.now()
				#format date of last api call for later in the script
				last_api_call = today.strftime("%H:%M  %m-%d-%Y")
				#get response status and format as text
				api_call_status = str(response.status_code)
				#check response was good, if call was bad skip to updating airtable last_api_call and api_call_status
				if api_call_status == '200':
					#return and format json file
					collection_json = response.text
					collection_array = json.loads(collection_json)
					#get predefined value from the API
					floor_price = str(collection_array["collection"]["stats"]["floor_price"])
					seven_day_price_change = str(collection_array["collection"]["stats"]["seven_day_change"])
					thirty_day_price_change = str(collection_array["collection"]["stats"]["thirty_day_change"])
					#write today's price to the csv for use later in calculating 90 day price change
					write_price_to_csv(collection_slug,today,floor_price)
					#get the price of the collection 90 days ago
					price_ninety_days_ago = get_price_ninety_days_ago(today, collection_slug)
					#check that there actually is a price 90 days ago
					if price_ninety_days_ago != 'None':
						#calculate 90 day price change
						ninety_day_price_change = str(calculate_ninety_day_price_change(floor_price, price_ninety_days_ago))
					else:
						ninety_day_price_change = "N/a"
					#get predefined value from api
					number_tokens_total = str(int(collection_array["collection"]["stats"]["total_supply"]))
					#get number_tokens_listed from scraper
					number_tokens_listed = str(int(get_number_tokens_listed(collection_slug)))
					#calculate percentage tokens listed
					percentage_tokens_listed = str(calculate_percentage_tokens_listed(number_tokens_total, number_tokens_listed))
					#update airtable with the new values
					airtable.update(id, {'floor_price': floor_price, '7_day_price_change': seven_day_price_change, '30_day_price_change': thirty_day_price_change, '90_day_price_change': ninety_day_price_change, '90_day_price_change': ninety_day_price_change, 'number_tokens_total': number_tokens_total, 'number_tokens_listed': number_tokens_listed, 'percentage_tokens_listed': percentage_tokens_listed})
				#update airtable with the datetime of current api call
				airtable.update(id, {'last_api_call': last_api_call, 'api_call_status': api_call_status })

		#unless something goes wrong
		except Exception as e:
			print(e)
			pass

while True:
	#check if it's time to run the code
	if str(datetime.datetime.now().strftime("%H:%M")) == "09:00":
		print("Code is running....")
		try:
			#update collections
			update_collections()
			print("Code complete")
		except:
			#send an error notification if something goes wrong
			send_error_notification()
			print("An error has occurred")
			continue