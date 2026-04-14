import pandas as pd

# 测试荣誉合并功能
def test_consolidate_awards():
    # 创建测试数据
    test_data = pd.DataFrame({
        'player_id': [2651.0, 2651.0, 2651.0, 2651.0, 100.0],
        'goldenglovewinners_Season': ['2004–05', '2009–10', '2013–14', '2015–16', None]
    })
    
    print("原始测试数据:")
    print(test_data.to_string(index=False))
    
    # 应用合并逻辑
    def merge_awards(group):
        awards = group['goldenglovewinners_Season'].dropna().astype(str)
        if len(awards) > 1:
            unique_awards = []
            for award in awards:
                award_str = str(award).strip()
                if award_str and award_str != 'nan':
                    # 处理年份范围（如1992–93）
                    if '–' in award_str:
                        # 提取起始年份
                        start_year = award_str.split('–')[0]
                        unique_awards.append(start_year)
                    else:
                        unique_awards.append(award_str)
            
            # 去重并排序
            unique_awards = sorted(set(unique_awards))
            return ', '.join(unique_awards)
        elif len(awards) == 1:
            award_str = str(awards.iloc[0]).strip()
            if '–' in award_str:
                # 处理年份范围
                start_year = award_str.split('–')[0]
                return start_year
            return award_str
        else:
            return None
    
    # 按player_id分组合并
    merged = test_data.groupby('player_id').apply(
        lambda group: merge_awards(group), 
        include_groups=False
    )
    
    print("\n合并后的结果:")
    for player_id, result in merged.items():
        print(f"player_id {player_id}: {result}")

if __name__ == "__main__":
    test_consolidate_awards()
