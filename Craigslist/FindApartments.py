# To access the worldwideweb
from requests import get
# The parser
from bs4 import BeautifulSoup
# Organize the scraped data and don't get caught
import pandas as pd
import numpy as np
import gspread
import df2gspread as d2g
import email, smtplib, ssl

from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from random import randint
from time import sleep
from warnings import warn

# This will provide the newest, 3+ bedroom apartments within 2 miles of
# 94115
#APT_URL = 'https://sfbay.craigslist.org/d/apartments-housing-for-rent/search/apa?sort=date&availabilityMode=0&laundry=1&min_bedrooms=3&postal=94115&search_distance=2'
APT_URL_2BD = 'https://sfbay.craigslist.org/search/apa?sort=date&search_distance=2&postal=94115&min_bedrooms=2&max_bedrooms=2&availabilityMode=0&laundry=1&sale_date=all+dates'
MAX_BUDGET = 1700.0

APT_URL = 'https://sfbay.craigslist.org/d/apartments-housing-for-rent/search/apa?sort=date&availabilityMode=0&laundry={inunit_laundry}&min_bedrooms={min_bedrooms}&max_bedrooms={max_bedrooms}&postal={zip_code}&search_distance={search_radius}'
INPUT_FILE_NAME = 'input.txt'
OUTPUT_FILE_NAME = 'Apartments.csv'

# Some arbitrary defaults.  Assume infinite moneys
DICTIONARY = {
		'inunit_laundry': 0,
		'sender_email': None,
		'min_bedrooms': 0,
		'max_bedrooms': 1000000,
		'central_zip_code': 0,
		'search_radius': 1.0,
		'max_price': 1000000,
		'per_room_budget': 1000000,
		'reciever_emails': [],
		'neighborhoods_to_avoid': []
}

def get_user_query_input():
	with open(INPUT_FILE_NAME, 'r') as f:
		for line in f:
			if line.isspace():
				continue

			# If we have a repeated field.
			if ',' in line:
				input_pair = line.split(':')
				if len(input_pair) < 1:
					print('Error: line \{}\' is improperly formatted')
					return False
				key = input_pair[0]
				repeated_field = input_pair[1].split(',')
				print(repeated_field)
				DICTIONARY[key] = [x.strip() for x in repeated_field]
			# For singleton fields.
			else:
				input_pair = line.split(':')
				if len(input_pair) != 2:
					print('Error: \'{}\' was not formatted properly.'.format(line))
					return False
				DICTIONARY[input_pair[0]] = input_pair[1]
		return True
	return False


# Return the attribute list for the apt page - to be parsed later
def get_apartments(apt_url):
	# Try to throw off CL's spider catchers.
	sleep(randint(1, 3))
	headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.13; rv:63.0) Gecko/20100101 Firefox/63.0'}
	response = get(apt_url, headers=headers)
	if response.status_code != 200:
		warn('Status code: {}'.format(response.status_code))

	html_soup = BeautifulSoup(response.text, 'html.parser')
	return html_soup.find_all('li', class_='result-row')


def parse_apartment_metadata(apt_post):
	try:
		price = float(
			apt_post.find(
				'span', class_='result-price').text[1:].replace(',', ''))
		num_bedrooms = int(
			apt_post.find('span', class_='housing').text.strip()[0])
		post_link = apt_post.find('a', class_='result-title hdrlnk')['href']
		post_title = apt_post.find('a', class_='result-title hdrlnk').text
		post_datetime = apt_post.find('time', class_='result-date')['datetime']
		return (price, num_bedrooms, post_link, post_title, post_datetime)
	except:
		return None


def filter_by_group_preferences(apt_title):
	title = apt_title.lower()
	for nbhd in DICTIONARY['neighborhoods_to_avoid']:
		if nbhd in title:
			return True
	return False
	

def mail_csv_to_recievers(csv_filename):
	# Send as email attachment to Robert and Corey
	sender = DICTIONARY['sender_email']
	receivers = DICTIONARY['reciever_emails']
	for f in receivers:
		print(f)
	port = 465  # For SSL
	password = input("Type your password (for your email) and press enter: ")

	# Create a secure SSL context
	context = ssl.create_default_context()

	body = 'This is an email from your friendly neighborhood spider, Charlotte :)'
	message = MIMEMultipart()
	message['From'] = sender
	message['Subject'] = 'Apartments to check out'
	message.attach(MIMEText(body, 'plain'))

	with open(csv_filename, 'rb') as attachment:
		part = MIMEBase('application', 'octet-stream')
		part.set_payload(attachment.read())

	encoders.encode_base64(part)

	part.add_header(
		"Content-Disposition",
		f"attachment; filename= {csv_filename}",)
	message.attach(part)


	with smtplib.SMTP_SSL("smtp.gmail.com", port, context=context) as server:
		server.login("lil.c.pup@gmail.com", password)
		for receiver in receivers:
			message['To'] = receiver
			text = message.as_string()
			server.sendmail(sender, receiver, text)

def main():
	if not get_user_query_input():
		print('Error when parsing the input file')
		return

	result_data = []
	apts = get_apartments(APT_URL.format(
		inunit_laundry=DICTIONARY['inunit_laundry'],
		min_bedrooms=DICTIONARY['min_bedrooms'],
		max_bedrooms=DICTIONARY['max_bedrooms'],
		zip_code=DICTIONARY['central_zip_code'],
		search_radius=DICTIONARY['search_radius']
		))

	for apt in apts:
		price, num_beds, link, title, timestamp = parse_apartment_metadata(apt)
		if (price / num_beds > float(DICTIONARY['per_room_budget'])
			or filter_by_group_preferences(title)):
			continue

		result_data.append([title, timestamp, num_beds, price, link])

	df = pd.DataFrame(data=result_data, columns=['title', 'time', 'beds',
												 'price', 'link'])
	df = df.drop_duplicates(subset='link')
	df.to_csv(OUTPUT_FILE_NAME, index=True)
	print('''	Done writing... May terminate if you like.\n
				{} apartments were written.'''.format(len(result_data)))

	mail_csv_to_recievers(OUTPUT_FILE_NAME)

if __name__ == '__main__':
	main()
