from collections import defaultdict
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException, WebDriverException, StaleElementReferenceException
from datetime import datetime
from time import time, sleep
from pprint import pprint
import os
import threading
import pickle

def click_back():
    button = driver.find_element_by_xpath("//button[contains(text(), 'Back')]")
    button.click()

def delete_marquee():
    marquee = driver.find_element_by_tag_name('marquee')
    driver.execute_script("arguments[0].parentNode.removeChild(arguments[0]);", marquee)

def try_loop(fn, check=lambda x: True, max_wait=20):
    thread_return = []
    def thread_try():
        while True:
            try:
                output = fn()
                if check(output):
                    thread_return.append(output)
                    break
            except NoSuchElementException:
                sleep(0.5)
    
    t = threading.Thread(target=thread_try)
    t.daemon = True
    t.start()
    t.join(timeout=max_wait)
    if not len(thread_return):
        raise TimeoutError()
    return thread_return.pop()

def get_time():
    now = datetime.now()
    return now.strftime("%Y/%m/%d %H:%M:%S")

def read_PM25():
    pm25s = try_loop(lambda: driver.find_elements_by_tag_name("td"), lambda cells: len(cells))
    if len(pm25s) < 5:
        print(get_time(), '      No data', flush=True)
        return {}
    min_PM25 = pm25s[2].text
    max_PM25 = pm25s[3].text
    avg_PM25 = pm25s[4].text
    return {
        'min_PM25': min_PM25,
        'max_PM25': max_PM25,
        'avg_PM25': avg_PM25,
    }

def read_month(ym_data):
    for day, day_data in ym_data.items():
        if len(day_data): continue
        cell, = try_loop(lambda: [td for td in driver.find_elements_by_class_name("green_Ava") if td.text == day], lambda cells: len(cells))
        print(get_time(), '   ', day, flush=True)
        cell.click()
        day_data.update(read_PM25())
        print(day_data)
        try_loop(click_back)

def read_site(site_data):
    for (year, month), ym_data in site_data.items():
        if all(len(d) for d in ym_data.values()):
            continue
        rows = try_loop(lambda: [tr for tr in driver.find_elements_by_tag_name("tr") if len(tr.find_elements_by_tag_name("td")) and tr.find_element_by_tag_name("td").text in ['2019', '2018']], lambda rows: len(rows))
        for tr in rows:
            if tr.find_element_by_tag_name("td").text == year:
                break
        column = tr.find_elements_by_tag_name("td")[int(month)]
        print(get_time(), ' ', year, month, flush=True)
        column.click()
        read_month(ym_data)
        try_loop(click_back)

def change_entry():
    # change the number of entries
    n_entries = driver.find_element_by_xpath("//select")
    option300 = n_entries.find_elements_by_tag_name('option')[1]
    driver.execute_script("arguments[0].value = '300';", option300) 
    driver.find_element_by_xpath("//select").send_keys('25')
    sleep(0.5)
    assert driver.find_element_by_xpath("//select").get_attribute('value') == '300'

with open('failed.txt', 'r') as f:
    failed_instances = [line.rstrip().split('|') for line in f.readlines()]
    failed_data = defaultdict(lambda: defaultdict(lambda: {}))
    for state, city, site, year, month, day in failed_instances:
        failed_data[state, city, site][year, month][day] = {}

driver = None

while True:
    try:
        link = 'https://app.cpcbccr.com/ccr/#/caaqm-dashboard-all/caaqm-landing/caaqm-data-availability'

        options = Options()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        driver = webdriver.Chrome(options=options)

        r = driver.get(link)
        print(get_time(), 'Loaded link', flush=True)
        param_search = try_loop(lambda: driver.find_element_by_xpath("//a[contains(text(), 'Search by Parameter Name')]"))
        param_search.click()
        print(get_time(), 'Switched to parameters', flush=True)
        button = try_loop(lambda: driver.find_element_by_xpath("//button[contains(text(), 'Submit')]"))
        button.click()
        delete_marquee()

        for (state, city, site), site_data in failed_data.items():
            if all(len(d) for ym in site_data.values() for d in ym.values()):
                continue
            try_loop(change_entry)
            tr, = try_loop(lambda: [tr for tr in driver.find_elements_by_tag_name("tr") if [x.text for x in tr.find_elements_by_tag_name("td")[1:4]] == [state, city, site]], lambda rows: len(rows))
            print(get_time(), state, city, site, flush=True)

            tr.find_element_by_tag_name("span").click()
            read_site(site_data)
            try_loop(click_back)
        break

    except (TimeoutError, ElementClickInterceptedException, WebDriverException, StaleElementReferenceException):
        driver is not None and driver.quit()
        print(get_time(), 'Reset', flush=True)

failed_data = [failed_data[state, city, site][year, month][day] for state, city, site, year, month, day in failed_instances]
import json
with open('failed_data.json', 'w') as f:
    json.dump(failed_data, f)