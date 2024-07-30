from bs4 import BeautifulSoup
import requests
import csv, time
from datetime import datetime

'''
住宅情報サイトであるsuumo(https://suumo.jp/)から、
川崎市に掲載されている物件を取得するスクレイピングプログラムです。
requestsとBeautifulSoupを使って、ページのリクエスト及び得られた情報の解析を実施しています。
ローカルにtsvファイルを作成し、ユーザーが手動でスプレッドシートにそのままコピー&ペーストする想定です。
貼付例：https://docs.google.com/spreadsheets/d/1QKeUgqrl8iYG5tDogs-O-wHQHKUbq69X7GaZuq9pABw/edit?hl=ja&gid=0#gid=0
'''

# ベースURL
URL = 'https://suumo.jp/jj/chintai/ichiran/FR301FC001/?ar=030&bs=040&ta=14&sa=02&sngz=&po1=25&pc=50'
# tsvファイルの保存先
SAVE_DIR = 'suumo.tsv'

def request_home_data_soup(request_url):
    '''
    物件一覧ののページをリクエストし、BeautifulSoupの解析結果を返す
    :param request_url:リクエストURL
    :return:BeautifulSoupの解析結果
    '''
    response = requests.get(request_url)
    assert response.status_code == 200, f'ステータスコード{str(response.status_code)}が返却されました。 url:{request_url}'
    soup = BeautifulSoup(response.text, 'lxml')
    # DOS防止。
    time.sleep(3)

    return soup


def get_passed_time():
    '''
    プログラム実行開始時間からの経過時間を返す
    :return: 現在時刻、経過時間
    '''
    now = datetime.now()
    passed_seconds = (now - start_time).seconds
    # 数値を文字列に変換した上で、2桁にする
    lmd_zf_value = lambda x: str(int(x)).zfill(2)
    # hh:mm:ssの形にする
    passed_time = ':'.join(
        [lmd_zf_value(passed_seconds / 3600), lmd_zf_value(passed_seconds / 60), lmd_zf_value(passed_seconds % 60)])

    return now.strftime('%m/%d %H:%M:%S'), passed_time


def extract_home_data(soup, current_home_index):
    '''
    ページの解析結果から、物件情報を取得する
    :param soup: ページの解析結果
    :param current_home_index:抽出した物件数(建物ごと)
    :return: 物件情報
    '''
    # タグ要素からテキストを抜き出す
    lmd_get_inner_text = lambda tag, selector: tag.select_one(selector).text.strip()


    def create_spreadsheet_func(func_name,*args):
        '''
        スプレッドシートへ貼付した時、関数として認識されるように文字列を調整する
        :param func_name: スプレッドシート上での関数名
        :param args: 関数化する時の引数
        :return: 調整後の文字列
        '''
        args = ','.join([f'"{arg}"' for arg in args])
        return f'={func_name}({args})'

    # 遷移先URL
    web_home_data_list = soup.select('div.cassetteitem')

    ret_home_data_list = []
    for home_index, web_home_data in enumerate(web_home_data_list, current_home_index):

        # 賃貸タイプ(アパート or マンション or 一軒家)
        rent_type = lmd_get_inner_text(web_home_data, 'div.cassetteitem_content-label > span').replace('賃貸', '')
        # 建物名
        home_name = lmd_get_inner_text(web_home_data, 'div.cassetteitem_content-title')
        # 住所
        address = lmd_get_inner_text(web_home_data, 'ul.cassetteitem_detail > li.cassetteitem_detail-col1')
        # 物件へのアクセス
        raw_access_list = lmd_get_inner_text(web_home_data,
                                             'ul.cassetteitem_detail > li.cassetteitem_detail-col2').split('\n')
        # アクセス数が3つに満たない時は、空文字で3つにする。
        # (スプレッドシート貼付時に列がずれてしまうため)
        raw_access_list += ['' for _ in range(3 - len(raw_access_list))]
        # アクセスを路線、最寄駅、最寄駅からの移動に分割
        # 例：京王相模原線/京王稲田堤駅 歩3分　→ # 京王相模原線、京王稲田堤駅、歩3分
        access_list = []
        for raw_access in raw_access_list:
            if '/' in raw_access and '分' == raw_access[-1]:
                train, station_distance = raw_access.split('/')
                station, distance = station_distance.split(' ')[0], ' '.join(station_distance.split(' ')[1:])
            else:
                train, station, distance = '', '', raw_access
            access_list.extend([train, station, distance])

        # 築年数・階数
        age, floor_num = lmd_get_inner_text(web_home_data,
                                            'ul.cassetteitem_detail > li.cassetteitem_detail-col3').split('\n')
        # 物件外観URL
        if (home_image_tag := web_home_data.select_one('img.js-noContextMenu.js-linkImage.js-adjustImg')):
            home_image = create_spreadsheet_func('IMAGE',home_image_tag.get('rel'))
        else:
            home_image = '画像なし'

        # 部屋情報リスト
        web_room_data_list = web_home_data.select('table.cassetteitem_other tbody > tr')

        for room_index, web_room_data in enumerate(web_room_data_list):
            # 階数
            floor = lmd_get_inner_text(web_room_data, 'td:nth-child(3)')
            # 賃料・管理費
            rent_fee, service_charge = lmd_get_inner_text(web_room_data, 'td:nth-child(4)').split('\n')
            rent_fee = rent_fee.replace('万円','').replace('-','0')
            service_charge = service_charge.replace('円','').replace('-','0')
            # 敷金・礼金
            security_deposit, key_money = lmd_get_inner_text(web_room_data, 'td:nth-child(5)').split('\n')
            security_deposit = security_deposit.replace('万円','').replace('-','0')
            key_money = key_money.replace('万円','').replace('-','0')
            # 間取り・専有面積
            layout, area = lmd_get_inner_text(web_room_data, 'td:nth-child(6)').split('\n')
            area = area.replace('m2','')
            # 間取り図
            if (layout_image_tag := web_room_data.select_one('td:nth-child(2) img')):
                layout_image = create_spreadsheet_func('IMAGE', layout_image_tag.get('rel'))
            else:
                layout_image = '画像なし'
            # 部屋詳細URL
            if (room_url_tag := web_room_data.select_one('.ui-text--midium.ui-text--bold > a')):
                room_url = create_spreadsheet_func('HYPERLINK', f'https://suumo.jp{room_url_tag.get("href")}','リンク')
            else:
                room_url = '部屋詳細ページなし'

            ret_home_data_list.append([home_index, room_index, rent_type, home_name, address]
                                      + access_list + [age, floor_num]
                                      + [floor, rent_fee, service_charge, security_deposit, key_money, layout, area,
                                         home_image, layout_image, room_url])

            now, passed_time = get_passed_time()
            print(now, passed_time, page_num, home_index, room_index, address, rent_fee, layout, area, sep='\t')

    return home_index, ret_home_data_list


# tsvファイルを作成し、ヘッダーを書き込む
with open(SAVE_DIR, mode='w') as f:
    csv.writer(f, delimiter='\t').writerow(['物件番号', '部屋番号', '賃貸タイプ', '建物名', '住所',
                                            '利用路線_1', '最寄駅_1', '最寄駅から_1',
                                            '利用路線_2', '最寄駅_2', '最寄駅から_2',
                                            '利用路線_3', '最寄駅_3', '最寄駅から_3',
                                            '築年数', '総階数', '階数', '賃料(万円)',
                                            '管理費(円)', '敷金(万円)', '礼金(万円)', '間取り', '専有面積(m2)',
                                            '物件外観', '間取り図', '部屋詳細'])

# サイトの末尾から物件データを取得
soup = request_home_data_soup(f'{URL}&page=1')
start_page_num = int(soup.select('div.pagination.pagination_set-nav li')[-1].text)
home_index = 0
start_time = datetime.now()
for page_num in range(start_page_num, 0, -1):
    request_url = f'{URL}&page={str(page_num)}'
    soup = request_home_data_soup(request_url)
    print(request_url)
    home_index, home_data_list = extract_home_data(soup, home_index)

    # tsv形式で保存
    with open(SAVE_DIR, mode='a', newline='') as f:
        csv.writer(f, delimiter='\t').writerows(home_data_list)

print('正常終了')
