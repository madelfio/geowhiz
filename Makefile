GEONAMES_DUMP_URL = http://download.geonames.org/export/dump
S3_BUCKET_URL = https://s3.amazonaws.com/madelfio-files
DOWNLOAD_PATH = /tmp/geowhiz-downloads
DEPS = $(addprefix $(DOWNLOAD_PATH)/,allCountries.txt alternateNames.txt admin1CodesASCII.txt admin2Codes.txt featureCodes_en.txt countryInfo.txt)

ALL: gaz.db

$(DOWNLOAD_PATH)/:
	mkdir -p $(DOWNLOAD_PATH)

$(DOWNLOAD_PATH)/s3-%:
	mkdir -p $(dir $@)
	curl -L -o $@ $(S3_BUCKET_URL)/$*

$(DOWNLOAD_PATH)/%: | $(DOWNLOAD_PATH)/
	mkdir -p $(dir $@)
	curl -L -o $@ $(GEONAMES_DUMP_URL)/$*

#$(DOWNLOAD_PATH)/%.zip: | $(DOWNLOAD_PATH)/
#	curl -L -o $@ $(GEONAMES_DUMP_URL)/$*.zip
#
#$(DOWNLOAD_PATH)/%.txt: | $(DOWNLOAD_PATH)/
#	curl -L -o $@ $(GEONAMES_DUMP_URL)/$*.txt

$(DOWNLOAD_PATH)/allCountries.txt: $(DOWNLOAD_PATH)/allCountries.zip
	unzip -u $< -d $(DOWNLOAD_PATH)

$(DOWNLOAD_PATH)/alternateNames.txt: $(DOWNLOAD_PATH)/alternateNames.zip
	unzip -u $< -d $(DOWNLOAD_PATH)

gaz.db: update_gaz.py $(DEPS)
	python update_gaz.py $(DOWNLOAD_PATH)

wikiranks: $(DOWNLOAD_PATH)/s3-georanks.txt include_georanks.py
	python include_georanks.py $<

clean:
	rm -rf $(DOWNLOAD_PATH) gaz.db
