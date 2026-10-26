対応する用語を持たないのは、業務の言葉では親の一部として語られる明細のエンティティ ([入荷明細](node:/sdd/data_design/logical_data_model/delivery_line)、[販売明細](node:/sdd/data_design/logical_data_model/sale_line)、[棚卸明細](node:/sdd/data_design/logical_data_model/stocktake_line)) である。

[販売](node:/sdd/data_design/logical_data_model/sale)と[販売明細](node:/sdd/data_design/logical_data_model/sale_line)を画面から登録することはない。販売が決済サービスからの通知として入るためで、この二つを参照する画面は、通知に未登録の書籍が含まれて保留になったときの[保留販売確認画面](node:/sdd/user_interface_design/SC08)だけである。同じ二つを表示する[書籍履歴画面](node:/sdd/user_interface_design/SC07)が項目の参照先を定めていないのは、入荷・販売・棚卸の三種を一つの履歴の表に畳んでいるためである。
