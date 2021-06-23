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

def read_each_month(month_data):
    cells = try_loop(lambda: driver.find_elements_by_class_name('green_Ava'), lambda cells: len(driver.find_elements_by_tag_name('td')))
    n_cells = len(cells)
    for i in range(n_cells):
        cell = cells[i]
        day = cell.text
        print(get_time(), '   ', day, flush=True)
        if day not in month_data:
            cell.click()
            month_data[day] = read_PM25()
            try_loop(click_back)
        cells = try_loop(lambda: driver.find_elements_by_class_name('green_Ava'), lambda cells: len(cells) == n_cells)
    month_data['done'] = True

def read_each_site(site_data):
    for row_index in 3, 4:
        rows = try_loop(
            lambda: driver.find_elements_by_tag_name("tr"),
            lambda rows: len(rows) and (len(rows) <= row_index or rows[row_index].find_element_by_tag_name("td").text.startswith('20')
        ))
        if len(rows) <= row_index: break
        year = rows[row_index].find_element_by_tag_name("td").text
        if year not in ['2019', '2018']:
            break
        for column_index in range(1, 13):
            column = rows[row_index].find_elements_by_tag_name("td")[column_index]
            if column.text != 'NA':
                print(get_time(), ' ', year, column_index, flush=True)
                if (year, column_index) not in site_data:
                    site_data[year, column_index] = {'done': False}
                if not site_data[year, column_index]['done']:
                    column.click()
                    read_each_month(site_data[year, column_index])
                    try_loop(click_back)
            rows = try_loop(
                lambda: driver.find_elements_by_tag_name("tr"),
                lambda rows: len(rows) and rows[row_index].find_element_by_tag_name("td").text in ['2019', '2018']
            )
    site_data['done'] = True

def change_entry():
    # change the number of entries
    n_entries = driver.find_element_by_xpath("//select")
    option300 = n_entries.find_elements_by_tag_name('option')[1]
    driver.execute_script("arguments[0].value = '300';", option300) 
    driver.find_element_by_xpath("//select").send_keys('25')
    sleep(0.5)
    assert driver.find_element_by_xpath("//select").get_attribute('value') == '300'

all_data = {}
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

        def get_station():
            stations = driver.find_elements_by_tag_name("tr")[1:]
            assert len(stations) == 292
            return stations[i]
        for i in range(int(os.environ['START']), int(os.environ['END'])):
            try_loop(change_entry)
            station = try_loop(get_station)
            state, city, site = [x.text for x in station.find_elements_by_tag_name('td')[1:4]]
            print(get_time(), state, city, site, flush=True)

            if os.path.exists(f'data/{"_".join([state, city, site])}.p'):
                continue
            if (state, city, site) not in all_data:
                all_data[state, city, site] = {'done': False}
            if not all_data[state, city, site]['done']:
                station.find_element_by_tag_name("i").click()
                read_each_site(all_data[state, city, site])
                try_loop(click_back)
            with open(f'data/{"_".join([state, city, site])}.p', 'wb') as f:
                pickle.dump(all_data[state, city, site], f)
        break

    except (TimeoutError, ElementClickInterceptedException, WebDriverException, StaleElementReferenceException):
        driver is not None and driver.quit()
        print(get_time(), 'Reset', flush=True)