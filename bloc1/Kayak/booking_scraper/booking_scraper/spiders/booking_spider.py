import csv
import os
import scrapy
from booking_scraper.items import HotelItem
from dotenv import load_dotenv


load_dotenv()


class BookingSpider(scrapy.Spider):
    name = 'booking'
    allowed_domains = ['booking.com']

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'CONCURRENT_REQUESTS': 1,
        'DOWNLOAD_DELAY': 3,
        'COOKIES_ENABLED': True,
    }

    def __init__(self, cities_csv=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.cities_csv = cities_csv
        self.cities = self.load_cities_from_csv()

        if not self.cities:
            self.logger.error(f"No cities found in {self.cities_csv}")
        else:
            self.logger.info(f"{len(self.cities)} cities found: {', '.join([_name for _id, _name in self.cities])}")

        aws_waf_token = os.getenv('AWS_WAF_TOKEN')
        if not aws_waf_token:
            raise ValueError(
                "AWS_WAF_TOKEN not found. Check that a .env file exists "
                "in the project (or a parent directory) and defines AWS_WAF_TOKEN."
            )
        self.cookies = {
            'aws-waf-token': aws_waf_token,
        }

        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:147.0) Gecko/20100101 Firefox/147.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            "Accept-Language": "fr,fr-FR;q=0.9,en-US;q=0.8,en;q=0.7",
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }

    def load_cities_from_csv(self):
        """Loads the list of cities from a CSV file"""
        cities = []

        if not os.path.exists(self.cities_csv):
            self.logger.error(f"File {self.cities_csv} not found")
            return cities

        try:
            with open(self.cities_csv, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter=';')

                if (
                        'city_id' not in reader.fieldnames or
                        'city_name' not in reader.fieldnames
                ):
                    self.logger.error(f"Columns 'city_id' or 'city_name' not found in {self.cities_csv}")
                    self.logger.info(f"Columns available: {reader.fieldnames}")
                    return cities

                for row in reader:
                    city_id = int(row.get('city_id', '').strip())
                    city_name = row.get('city_name', '').strip()
                    if city_id and city_name:
                        cities.append([city_id, city_name])

            return cities

        except Exception as e:
            self.logger.error(f"Error while reading the CSV file: {e}")
            return cities

    def start_requests(self):
        """Starting point: generate requests for each city"""

        for city_id, city_name in self.cities:
            url = f"https://www.booking.com/searchresults.fr.html?ss={city_name}&ltfd=5%3A2%3A1-2026%3A1%3A1&nflt=ht_id%3D204%3Breview_score%3D90%3Breview_score%3D80"
            yield scrapy.Request(
                url=url,
                cookies=self.cookies,
                headers=self.headers,
                callback=self.parse_search_results,
                meta={'city_id': city_id, 'city_name': city_name},
                dont_filter=True
            )

    def parse_search_results(self, response):
        """Parse the result web page to extract hotel information"""

        city_id = response.meta['city_id']
        city_name = response.meta['city_name']

        if 'challenge-container' in response.text:
            self.logger.error(f"Blocked by AWS WAF for {city_name}")
            return

        self.logger.info(f"Scraping {city_name}")

        hotels = response.css('[data-testid="property-card"]')

        if not hotels:
            self.logger.warning(f"No hotel found for {city_name}")
            return

        hotels_scraped = 0

        for hotel in hotels:

            url = hotel.css('a[data-testid="title-link"]::attr(href)').get().split("?")[0]
            name = hotel.css('div[data-testid="title"]::text').get()
            note_str = hotel.css('[data-testid="review-score"] div::text').re_first(r'\d+[,.]?\d*')

            if not name or not url:
                continue

            note = None
            if note_str:
                try:
                    note = float(note_str.replace(',', '.'))
                except ValueError:
                    pass

            item = HotelItem()
            item['city_id'] = city_id
            item['name'] = name.strip()
            item['note'] = note
            item['url'] = url
            item['address'] = None  # will be filled in parse_hotel_page
            item['description'] = None  # idem
            item['latitude'] = None  # idem
            item['longitude'] = None  # idem

            hotels_scraped += 1

            yield scrapy.Request(
                url=url,
                cookies=self.cookies,
                headers=self.headers,
                callback=self.parse_hotel_page,
                meta={'item': item},
                dont_filter=True
            )

            if hotels_scraped >= 20:
                break

        self.logger.info(f"{hotels_scraped} hotels found for {city_name}")

    def parse_hotel_page(self, response):
        """Parse the hotel web page on booking.com to extract its address and its description"""

        item = response.meta['item']

        if 'challenge-container' in response.text:
            self.logger.error(f"Blocked on this hotel web page: {item['name']}")
            # Return the item even if it is incomplete
            yield item
            return

        address = response.css(
            '[data-testid="PropertyHeaderAddressDesktop-wrapper"] button > div::text'
        ).get()
        address = address.replace('\xa0', ' ').strip() if address else None
        description_parts = response.css('[data-testid="property-description"] *::text').getall()
        description = ' '.join(description_parts).replace('\xa0', ' ').strip()
        coordinates = response.css('[data-atlas-latlng]::attr(data-atlas-latlng)').get().split(',')
        latitude, longitude = coordinates

        # Filling missing fields
        item['address'] = address.strip() if address else None
        item['description'] = description or None
        item['latitude'] = float(latitude.strip()) if latitude else 0.0
        item['longitude'] = float(longitude.strip()) if latitude else 0.0

        self.logger.info(f"Details retrieved for: {item['name']}")

        # Return the completed item
        yield item
