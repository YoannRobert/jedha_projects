import scrapy


class HotelItem(scrapy.Item):
    city_id = scrapy.Field()
    name = scrapy.Field()
    address = scrapy.Field()
    note = scrapy.Field()
    url = scrapy.Field()
    description = scrapy.Field()
    latitude = scrapy.Field()
    longitude = scrapy.Field()
