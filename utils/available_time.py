from datetime import datetime, timedelta, time
from typing import List, Tuple, Optional


def find_available_slot(
        busy_slots: List[Tuple[datetime, datetime]],
        hour_interval: float = 1.0,
        start_date: Optional[datetime] = None,
        max_days_to_search: int = 7
) -> List[Tuple[datetime, datetime]]:
    """
    查找指定天数内所有可用的连续时间段用于面试

    参数:
        busy_slots: 已占用时间段列表，每个元素为 (start_datetime, end_datetime)
        hour_interval: 需要的连续时长（小时），默认1.0小时
        start_date: 开始查找的日期（datetime类型），默认为明天00:00
        max_days_to_search: 最大搜索天数，避免无限循环，默认30天

    返回:
        (start, end) 元组列表表示找到的可用时间段；若未找到则返回空列表

    时间窗口规则:
        - 上午: 09:00 - 12:00
        - 下午: 14:00 - 18:00
    """
    # 1. 确定开始查找的日期（默认明天）
    if start_date is None:
        tomorrow = datetime.now().date() + timedelta(days=1)
        current_search_date = datetime.combine(tomorrow, time.min)
    else:
        tzinfo = start_date.tzinfo
        current_search_date = datetime.combine(
            start_date.date(),
            time.min,
            tzinfo=tzinfo,
        )

    # 2. 定义每日有效时间窗口（上午+下午）
    daily_windows = [
        (time(9, 0), time(12, 0)),  # 上午窗口
        (time(14, 0), time(18, 0))  # 下午窗口
    ]

    # 3. 预处理忙碌时段：过滤并标准化
    normalized_busy = []
    for start, end in busy_slots:
        # 修复结束时间早于开始时间的错误数据
        if end < start:
            start, end = end, start
        normalized_busy.append((start, end))

    available_slots: List[Tuple[datetime, datetime]] = []
    interval_delta = timedelta(hours=hour_interval)

    # 4. 逐日搜索可用时间段
    for day_offset in range(max_days_to_search):
        search_date = current_search_date + timedelta(days=day_offset)

        # 检查每个有效时间窗口
        for win_start_time, win_end_time in daily_windows:
            window_start = datetime.combine(
                search_date.date(),
                win_start_time,
                tzinfo=current_search_date.tzinfo,
            )
            window_end = datetime.combine(
                search_date.date(),
                win_end_time,
                tzinfo=current_search_date.tzinfo,
            )

            # 收集当天与当前窗口重叠的忙碌时段
            conflicts = []
            for busy_start, busy_end in normalized_busy:
                # 判断忙碌时段是否与当前窗口有交集
                if busy_end > window_start and busy_start < window_end:
                    # 计算实际重叠部分
                    actual_start = max(busy_start, window_start)
                    actual_end = min(busy_end, window_end)
                    if actual_end > actual_start:  # 确保有效重叠
                        conflicts.append((actual_start, actual_end))

            # 按开始时间排序冲突时段
            conflicts.sort(key=lambda x: x[0])

            # 5. 从窗口开始时间起，检查空闲间隙
            current_time = window_start
            for conflict_start, conflict_end in conflicts:
                # 把冲突前的空闲间隙切成多个 hour_interval 段
                while conflict_start - current_time >= interval_delta:
                    available_slots.append((current_time, current_time + interval_delta))
                    current_time += interval_delta

                # 更新当前时间到冲突结束后
                current_time = max(current_time, conflict_end)

            # 检查最后一个冲突后的空闲间隙
            while window_end - current_time >= interval_delta:
                available_slots.append((current_time, current_time + interval_delta))
                current_time += interval_delta

    return available_slots
