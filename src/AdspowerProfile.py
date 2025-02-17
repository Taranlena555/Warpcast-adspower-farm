from random import randint, uniform
from time import sleep, time
from platform import system
import json

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.keys import Keys
from loguru import logger

from data.config import config
from src.exceptions import AdspowerApiThrottleException


class AdspowerProfile:
    API_ROOT = 'http://local.adspower.com:50325'
    LAST_API_CALL_TIMESTAMP = 0

    def __init__(self, profile_name: str, profile_id: str):
        self.profile_name = profile_name
        self.profile_id = profile_id

        self.driver = None
        self.action_chain = None
        self.wait = None
        self.profile_was_running = None

        self.__init_profile_logs()

    @classmethod
    def wait_for_api_readiness(cls):
        logger.debug('Waiting for api readiness')
        while True:
            if time() - cls.LAST_API_CALL_TIMESTAMP < 2:
                sleep(1)
            else:
                logger.debug('Api ready')
                cls.LAST_API_CALL_TIMESTAMP = time()
                break

    def __init_profile_logs(self) -> None:
        logger.debug('__init_profile_logs: entered method')
        with open('data/profile_logs.json') as file:
            profile_logs = json.load(file)

        if self.profile_name not in profile_logs:
            profile_logs[self.profile_name] = {}

        if "mandatory_users_subscribes" not in profile_logs[self.profile_name]:
            profile_logs[self.profile_name]["mandatory_users_subscribes"] = []

        if "mandatory_channels_subscribes" not in profile_logs[self.profile_name]:
            profile_logs[self.profile_name]["mandatory_channels_subscribes"] = []

        if "wallet_connected" not in profile_logs[self.profile_name]:
            profile_logs[self.profile_name]["wallet_connected"] = False

        with open("data/profile_logs.json", "w") as file:
            json.dump(profile_logs, file, indent=4)

    def __init_webdriver(self, driver_path: str, debug_address: str) -> None:
        logger.debug(f'__init_webdriver: driver_path: {driver_path}')
        logger.debug(f'__init_webdriver: debug_address: {debug_address}')

        chrome_options = Options()
        caps = DesiredCapabilities().CHROME
        caps["pageLoadStrategy"] = "eager"

        chrome_options.add_experimental_option("debuggerAddress", debug_address)
        driver = webdriver.Chrome(executable_path=driver_path, options=chrome_options, desired_capabilities=caps)
        driver.implicitly_wait = config['element_wait_sec']
        self.driver = driver
        self.action_chain = ActionChains(self.driver)
        self.wait = WebDriverWait(self.driver, config['element_wait_sec'])

    @staticmethod
    def random_activity_sleep() -> None:
        logger.debug('random_activity_sleep: sleeping')
        sleep(randint(config["delays"]["min_activity_sec"], config["delays"]["max_activity_sec"]))
        logger.debug('random_activity_sleep: finished sleeping')

    @staticmethod
    def random_subactivity_sleep() -> None:
        logger.debug('random_subactivity_sleep: sleeping')
        sleep(randint(config["delays"]["min_subactivity_sec"], config["delays"]["max_subactivity_sec"]))
        logger.debug('random_subactivity_sleep: finished sleeping')

    def human_hover(self, element: WebElement, click: bool = False) -> None:
        logger.debug('human_hover: entered method')
        size = element.size

        width_deviation_pixels = randint(1, int(size["width"] * config["max_click_width_deviation"]))
        height_deviation_pixels = randint(1, int(size["height"] * config["max_click_height_deviation"]))

        positive_width_deviation = randint(0, 1)
        positive_height_deviation = randint(0, 1)

        x = width_deviation_pixels if positive_width_deviation else -width_deviation_pixels
        y = height_deviation_pixels if positive_height_deviation else -height_deviation_pixels

        if click:
            logger.debug(f'human_hover: hover + clicking "{element.text}"')
            self.action_chain.move_to_element_with_offset(element, x, y).perform()
            sleep(uniform(0.5, 2))
            self.action_chain.click().perform()
        else:
            logger.debug(f'human_hover: hover only "{element.text}"')
            self.action_chain.move_to_element_with_offset(element, x, y).perform()

    def human_scroll(self) -> None:
        logger.debug('human_scroll: entered method')
        ticks_per_scroll = randint(config['min_ticks_per_scroll'], config['max_ticks_per_scroll'])
        logger.debug(f'human_scroll: {ticks_per_scroll} ticks_per_scroll')
        for tick in range(ticks_per_scroll):
            sleep(uniform(config["min_delay_between_scroll_ticks_sec"], config["max_delay_between_scroll_ticks_sec"]))
            self.driver.execute_script(f"window.scrollBy(0, {config['pixels_per_scroll_tick']});")

    def human_type(self, text: str) -> None:
        logger.debug('human_type: entered method')
        text_lines = text.split(r'\n')

        for i, line in enumerate(text_lines):
            for char in line:
                sleep(uniform(config["delays"]["min_typing_sec"], config["delays"]["max_typing_sec"]))
                self.action_chain.send_keys(char).perform()

            if i != len(text_lines) - 1:
                self.action_chain.send_keys(Keys.ENTER).perform()
                sleep(uniform(config["delays"]["min_typing_sec"], config["delays"]["max_typing_sec"]))

    def human_clear_selected_input(self) -> None:
        logger.debug('human_clear_selected_input: entered method')
        key_to_hold = Keys.CONTROL if system() == 'Windows' else Keys.COMMAND
        self.action_chain.key_down(key_to_hold).send_keys('a').key_up(key_to_hold).perform()
        sleep(uniform(0.1, 1))
        self.action_chain.send_keys(Keys.BACKSPACE).perform()

    def open_profile(self, headless: bool = False) -> None:
        url = AdspowerProfile.API_ROOT + '/api/v1/browser/active'
        params = {
            "user_id": self.profile_id,
        }

        AdspowerProfile.wait_for_api_readiness()
        is_active_response = requests.get(url, params=params).json()
        logger.debug(f'open_profile: is_active_response: {is_active_response}')

        if is_active_response["code"] == -1:
            raise AdspowerApiThrottleException()
        elif is_active_response["code"] != 0:
            raise Exception('Failed to check profile open status')

        if is_active_response['data']['status'] == 'Active':
            self.profile_was_running = True
            if not config["farm_running_profiles"]:
                raise Exception('Profile is active')

            self.__init_webdriver(is_active_response["data"]["webdriver"], is_active_response["data"]["ws"]["selenium"])

        else:
            self.profile_was_running = False
            url = AdspowerProfile.API_ROOT + '/api/v1/browser/start'
            params = {
                "user_id": self.profile_id,
                "open_tabs": "0",
                "ip_tab": "0",
                "headless": "1" if headless else "0",
            }

            AdspowerProfile.wait_for_api_readiness()
            start_response = requests.get(url, params=params).json()
            logger.debug(f'open_profile: start_response: {start_response}')

            if start_response["code"] == -1:
                raise AdspowerApiThrottleException()
            elif start_response["code"] != 0:
                raise Exception(f'Failed to open profile, server response: {start_response}')

            self.__init_webdriver(start_response["data"]["webdriver"], start_response["data"]["ws"]["selenium"])

    def close_profile(self) -> None:
        url_check_status = AdspowerProfile.API_ROOT + '/api/v1/browser/active' + f'?user_id={self.profile_id}'
        url_close_profile = AdspowerProfile.API_ROOT + '/api/v1/browser/stop' + f'?user_id={self.profile_id}'

        AdspowerProfile.wait_for_api_readiness()
        status_response = requests.get(url_check_status).json()

        if status_response["code"] == -1:
            raise AdspowerApiThrottleException()
        elif status_response["code"] != 0:
            raise Exception('Failed to check profile open status')

        if status_response['data']['status'] == 'Inactive':
            self.driver = None
            self.action_chain = None
            return

        AdspowerProfile.wait_for_api_readiness()
        close_response = requests.get(url_close_profile).json()

        if close_response["code"] == -1:
            raise AdspowerApiThrottleException()
        elif close_response["code"] != 0:
            raise Exception('Failed to close profile')

        self.driver = None

    def switch_to_tab(self, url_includes_text: str) -> None:
        logger.debug('__switch_to_tab: entered method')
        logger.debug(f'__switch_to_tab: looking for tab that includes "{url_includes_text}"')
        for tab in self.driver.window_handles:
            try:
                self.driver.switch_to.window(tab)
                if url_includes_text in self.driver.current_url:
                    logger.debug(f'__switch_to_tab: switched to window "{self.driver.current_url}"')
                    return
            except Exception:
                pass

        raise Exception(f'Failed to find tab that includes {url_includes_text} in url')

    def wait_for_new_tab(self, init_tabs: list[str]) -> None:
        logger.debug('__wait_for_new_tab: entered method')
        for i in range(config["element_wait_sec"]):
            if list(set(self.driver.window_handles) - set(init_tabs)):
                logger.debug('__wait_for_new_tab: found new tab')
                return
            else:
                sleep(1)

        raise Exception('Failed to locate new tab or extension window')

    def close_all_other_tabs(self) -> None:
        initial_tab = self.driver.current_window_handle
        tabs_to_close = self.driver.window_handles
        tabs_to_close.remove(initial_tab)

        for tab in tabs_to_close:
            self.driver.switch_to.window(tab)
            self.driver.close()

        self.driver.switch_to.window(initial_tab)
