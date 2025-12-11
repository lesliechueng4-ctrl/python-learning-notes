import requests
import json
import logging
import os
import time

# 全局常量和日志器初始化
SD = os.path.split(os.path.realpath(__file__))[0]
logger = logging.getLogger(__file__.split("/")[-1])
handler1 = logging.StreamHandler()
handler2 = logging.FileHandler(filename=SD + "/citybox_log.csv")
logger.setLevel(logging.DEBUG)
handler1.setLevel(logging.INFO)
handler2.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s, %(name)s,%(lineno)d, %(levelname)s, %(message)s", datefmt='%Y-%m-%d %H:%M:%S')
handler1.setFormatter(formatter)
handler2.setFormatter(formatter)
logger.addHandler(handler1)
logger.addHandler(handler2)

class Citybox:

    def __init__(self):
        # 检查配置文件是否存在
        conf_path = os.path.join(SD, 'citybox_conf.json')
        if not os.path.exists(conf_path):
            logger.warning("Citybox 配置文件不存在: %s" % conf_path)
            raise FileNotFoundError(f"配置文件未找到: {conf_path}")
        # 加载配置信息、账号信息、token
        with open(conf_path, 'r', encoding='utf-8') as f:
            self.conf = json.load(f)
        self.account_info = self.conf['ACCOUNT_INFO'].copy()

    def _get_auth(self, account, need_cookie=False):
        """
        统一获取请求头、token、cookie
        :param account: 账号名
        :param need_cookie: 是否需要cookie
        :return: headers, token, cookies（可选）
        """
        headers = self.conf['HEADER'].copy()
        token = self.account_info[account]['token']
        headers.update({'token': token})
        if need_cookie:
            cookies = self.account_info[account].get('cookie', {}).copy()
            cookies.update({'token': token})
            return headers, token, cookies
        return headers, token

    def check(self, account) -> bool:
        """
        检查token是否过期，没有过期，更新last sign、last modou
        :param account:
        :return: Boolean
        """
        # 初始化请求头
        headers, token = self._get_auth(account)
        # 发送请求
        status_response = requests.get(self.conf['GET_USER_INFO_URL'], headers=headers)
        if status_response.status_code == 200:
            json_formatted_text = status_response.json()
            self.account_info[account]['last_modou'] = int(json_formatted_text['modou'])
            self.account_info[account]['last_sign'] = json_formatted_text['last_update']
            self.account_info[account]['hassign'] = json_formatted_text['hassign']
            self.account_info[account]['token_expire'] = False
            return True
        elif status_response.status_code == 401:  # token 过期
            logger.warning('Citybox Account %s: Error 401. Token maybe expired.' % account)
            self.account_info[account]['token_expire'] = True
            return False
        else:
            logger.warning('Citybox Account %s: Error code:%s.' % (account, status_response.status_code))
            return False

    def check_modou(self, account) -> int:
        """
        显示账号当前魔豆数量
        :param account:
        :return: Int
        """
        # 初始化请求头
        headers, token = self._get_auth(account)
        # 发送请求
        status_response = requests.get(self.conf['GET_USER_INFO_URL'], headers=headers)
        if status_response.status_code == 200:
            json_formatted_text = status_response.json()
            current_modou = int(json_formatted_text['modou'])
            return current_modou
        else:
            return 0

    def check_lottery(self, account) -> bool:

        lottery_status_info = ''
        lost_amount = 0
        win_amount = 0

        # 初始化请求头和cookies
        headers, token = self._get_auth(account)

        try:
            # 发送请求
            lottery_amount_response = requests.post(self.conf['LOTTERY_LOG_URL'], headers=headers, data={"up_status": 3})
            if lottery_amount_response.status_code == 200:
                json_formatted_text = lottery_amount_response.json()
                lost_amount = len(json_formatted_text)

                # 发送请求
                lottery_log_response = requests.post(self.conf['LOTTERY_LOG_URL'], headers=headers, data={"up_status": 2})
                if lottery_log_response.status_code == 200:
                    json_formatted_text = lottery_log_response.json()
                    win_amount = len(json_formatted_text)
                    no_receive_amount = 0
                    no_receive_lottery_name = ''
                    for lottery_log in json_formatted_text:
                        if lottery_log['lottery_status'] == '2':
                            if lottery_log['delivery_status'] == '1' and lottery_log['expire_state'] == 1:
                                no_receive_amount += 1
                                no_receive_lottery_name += lottery_log['name'] + " " + lottery_log['log_id']
                                data_ = {"log_id": lottery_log['log_id']}
                                try:
                                    lottery_receive_response = requests.get(self.conf['LOTTERY_RECEIVE_URL'], headers=headers, params=data_)
                                    if lottery_receive_response.status_code == 200:
                                        logger.info('Citybox Account %s : Received Lottery %s' % (account, lottery_log['name']))
                                        no_receive_lottery_name += " " + lottery_receive_response.text.encode().decode('unicode-escape') + "\n"
                                    else:
                                        no_receive_lottery_name += "\n"
                                except Exception as e:
                                    logger.warning(f'Citybox Account {account} : Lottery receive request exception: {e}')

                    lottery_status_info += "Citybox Account %s:\n" \
                                           "    Lottery Amount: %s\n" \
                                           "    Win Amount: %s\n" \
                                           % (account, win_amount + lost_amount, win_amount)

                    if no_receive_amount:
                        lottery_status_info += "    No Receive Amount: %s\n" \
                                               "    No Receive lottery: \n%s\n" \
                                               % (no_receive_amount, no_receive_lottery_name,)
                else:
                    logger.warning(
                        'Citybox Account %s : Lottery log request failed. Error code: %s' % (
                            account, lottery_log_response.status_code))
        except Exception as e:
            logger.warning(f'Citybox Account {account} : Lottery log request exception: {e}')

        return True

    def check_coupon(self, account) -> bool:

        coupon_status_info = ""

        # 初始化请求头和cookies
        headers, token = self._get_auth(account)
        headers.update({'sign': '30901107d96c036da007f6301b9532a9'})
        # headers.update({'sign': '4ab11123eac2306ce0018ae323b6d880'})

        try:
            # 发送请求
            coupon_list_response = requests.get(self.conf['COUPON_LIST_URL'], headers=headers,
                                                params={'status': '0', 'page': '1', 'page_size': '100'})
            if coupon_list_response.status_code == 200:
                json_formatted_text = coupon_list_response.json()
                coupons_name = ""
                for coupon in json_formatted_text:
                    if "元" in coupon['card_name']:
                        coupons_name += "\t\t\t\t\t%s %s\n" % (coupon['card_name'], coupon['to_date'])

                coupon_status_info += "Citybox Account %s:\nCoupon no used:\n%s" % (account, coupons_name,)

            else:
                logger.warning(
                    'Citybox Account %s : Coupon request failed. Error code: %s' % (
                        account, coupon_list_response.status_code))

            if coupons_name:
                logger.info(coupon_status_info.replace('\n', ''))
        except Exception as e:
            logger.warning(f'Citybox Account {account} : Coupon request exception: {e}')

        return True

    def collect_modou(self) -> bool:
        """
        收集魔豆
        :return: Boolean
        """

        for user in self.account_info:
            if self.check(user):
                self.sign_in(user)
                self.roulette(user)
                self.roulette(user)
                self.check_lottery(user)
                self.lottery(user)
                # self.check_coupon(user)
                time.sleep(1)
                self.compare_modou(user)

        # 通过wechat 发消息
        # self.send_wechat()

        # 更新account info至citybox_conf.json
        self.update_account_info()

        return True

    def compare_modou(self, account) -> bool:
        """
        比较modou变化，更新
        :param account:
        :return: Boolean
        """
        current_modou = self.check_modou(account)
        difference = current_modou - self.account_info[account]['last_modou']
        self.account_info[account]['difference'] = difference
        self.account_info[account]['current_modou'] = current_modou
        logger.info('Citybox Account %s : modou: %s' % (account, self.account_info[account]['current_modou']))
        return True

    def roulette(self, account) -> bool:
        """
        魔盒大转盘抽奖
        :param account:
        :return: Boolean
        """
        # 初始化请求头和cookies
        headers, token, cookies = self._get_auth(account, need_cookie=True)
        try:
            # 发送请求
            roulette_response = requests.post(self.conf['ROULETTE_URL'], headers=headers, cookies=cookies)
            if roulette_response.status_code == 200:
                json_formatted_text = roulette_response.json()
                prize = json_formatted_text['winning_desc']
                logger.info('Citybox Account %s: Prize: %s.' % (account, prize))
                return True
            elif roulette_response.status_code == 400:
                json_formatted_text = roulette_response.json()
                logger.warning('Citybox Account %s: %s.' % (account, json_formatted_text['message']))
                return False
            else:
                logger.warning(
                    'Citybox Account %s : Request failed. Error code: %s' % (account, roulette_response.status_code))
                return False
        except Exception as e:
            logger.warning(f'Citybox Account {account} : Roulette request exception: {e}')
            return False

    def lottery(self, account) -> bool:
        # 初始化请求头
        headers, token = self._get_auth(account)
        try:
            # 发送请求
            lottery_info_response = requests.post(self.conf['LOTTERY_INFO_URL'], headers=headers)
            if lottery_info_response.status_code == 200:
                json_formatted_text = lottery_info_response.json()

                for lottery in json_formatted_text:
                    if not ("积分" in lottery['name'] or "无门槛" in lottery['name']):
                        continue
                    if lottery['is_join'] == 0:
                        data = {"lottery_id": lottery['lottery_id']}
                        try:
                            lottery_response = requests.post(self.conf['LOTTERY_URL'], headers=headers, data=data)
                            if lottery_response.status_code == 200:
                                json_formatted_text = lottery_response.json()
                                if json_formatted_text == "参与成功":
                                    logger.info("Citybox Account %s: Join lottery %s" % (account, lottery['name']))
                                else:
                                    logger.warning(
                                        'Citybox Account %s : Join lottery request failed. Error msg: %s' % (
                                            account, json_formatted_text))
                            else:
                                logger.warning(
                                    'Citybox Account %s : Lottery request failed. Error code: %s' % (
                                        account, lottery_info_response.status_code))
                                return False
                        except Exception as e:
                            logger.warning(f'Citybox Account {account} : Join lottery request exception: {e}')
            else:
                logger.warning(
                    'Citybox Account %s : Lottery info request failed. Error code: %s' % (
                        account, lottery_info_response.status_code))
                return False
        except Exception as e:
            logger.warning(f'Citybox Account {account} : Lottery info request exception: {e}')
            return False

    def sign_in(self, account) -> bool:
        """
        魔盒签到
        :param account:
        :return: Boolean
        """
        # 初始化请求头
        headers, token = self._get_auth(account)
        # 检查当日是否signin
        last_sign = self.account_info[account]['hassign']
        if last_sign == 0:
            try:
                # 发送signin请求
                sign_in_response = requests.get(self.conf['SIGN_URL'], headers=headers)
                if sign_in_response.status_code == 200:
                    qmodou = sign_in_response.json()['qmodou']  # 获取签到魔豆数量
                    logger.info('Citybox Account %s: Sign in successful. %s modous added.' % (account, qmodou))
                    return True
                else:
                    logger.info('Citybox Account %s: Failed. Respons code: %s.' % (account, sign_in_response))
                    return False
            except Exception as e:
                logger.warning(f'Citybox Account {account} : Sign in request exception: {e}')
                return False
        else:
            logger.warning(
                'Citybox Account %s: Failed. Signed in on %s .' % (account, self.account_info[account]['last_sign']))
            return False

    def update_account_info(self):
        """
        更新账号信息至citybox_conf.json
        :return: Boolean
        """
        with open('citybox_conf.json', 'w', encoding='utf8')as f:
            self.conf['ACCOUNT_INFO'] = self.account_info
            json.dump(self.conf, f, ensure_ascii=False, indent=2)
        return True


if __name__ == '__main__':

    logger.info('Start citybox job.')
    citybox = Citybox()

    if citybox:
        if citybox.collect_modou():
            logger.info("Citybox collect modou success.")
        else:
            logger.warning("Citybox collect modou failed. Check log.")
    else:
        logger.warning("Citybox instantiate failed. No citybox conf file.")
    logger.info("End citybox job.")
