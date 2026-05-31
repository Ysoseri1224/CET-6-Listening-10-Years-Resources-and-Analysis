"""
CET-6 听力真题数据分析脚本
用于生成 episode-10.md 中所有数据结论的完整分析流程。

使用方法：
    python analyze_listening.py

依赖：仅标准库（pathlib, re, collections, statistics, itertools, random）
"""

import re
import os
import statistics
import random
from pathlib import Path
from collections import Counter, defaultdict
from itertools import combinations

BASE_DIR = Path(__file__).parent

STOP_WORDS = {
    'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
    'should', 'may', 'might', 'shall', 'can', 'to', 'of', 'in', 'for',
    'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through', 'during',
    'before', 'after', 'above', 'below', 'between', 'and', 'but', 'or',
    'nor', 'not', 'so', 'yet', 'both', 'either', 'neither', 'each',
    'every', 'all', 'any', 'few', 'more', 'most', 'other', 'some',
    'such', 'no', 'only', 'own', 'same', 'than', 'too', 'very',
    'just', 'because', 'if', 'when', 'where', 'how', 'what', 'which',
    'who', 'whom', 'this', 'that', 'these', 'those', 'it', 'its',
    'he', 'she', 'they', 'them', 'his', 'her', 'their', 'my', 'your',
    'our', 'me', 'him', 'us', 'i', 'you', 'we', 'about', 'up', 'out',
    'then', 'there', 'here', 'also', 'much', 'many', 'well', 'back',
}

TRANSITION_WORDS = re.compile(
    r'\b(but|however|although|yet|while|instead|actually|in fact|nevertheless|'
    r'nonetheless|on the other hand|rather|still)\b', re.IGNORECASE
)

SUGGESTION_WORDS = re.compile(
    r'\b(suggest|recommend|why don\'t|how about|why not|you should|'
    r'you could|you might|let\'s|shall we|would you like to)\b', re.IGNORECASE
)

ABSOLUTE_WORDS = re.compile(
    r'\b(always|never|none|completely|impossible|absolutely|entirely|'
    r'all|every|only)\b', re.IGNORECASE
)


# ─── 文件解析 ───────────────────────────────────────────────────────────────

def find_exam_sets():
    """扫描目录，找出所有有效的题目集（stem + answer + transcript 三者齐全）"""
    sets = {}
    for d in sorted(BASE_DIR.iterdir()):
        if not d.is_dir() or not d.name.startswith('CET6_'):
            continue
        stems = list(d.glob('*_q_stem.txt'))
        answers = list(d.glob('*_q_answer.txt'))
        transcripts = list(d.glob('*_transcript.md'))
        for sf in stems:
            key = re.search(r'cet6_(.+?)_q_stem\.txt$', sf.name, re.I)
            if not key:
                continue
            k = key.group(1)
            af = d / f'cet6_{k}_q_answer.txt'
            tf = d / f'cet6_{k}_transcript.md'
            if af.exists() and tf.exists():
                sets[k] = {'stem': sf, 'answer': af, 'transcript': tf}
    return sets


def parse_stem(path):
    """解析题干文件，返回 [{qnum, options: {A: text, B: text, C: text, D: text}}]"""
    text = path.read_text(encoding='utf-8')
    questions = []
    current_q = None
    for line in text.split('\n'):
        line = line.rstrip()
        qm = re.match(r'^\s*(\d+)\.\s*([A-D])\)\s*(.+)', line)
        if qm:
            qnum = int(qm.group(1))
            current_q = {'qnum': qnum, 'options': {}}
            questions.append(current_q)
            current_q['options'][qm.group(2)] = qm.group(3).strip()
            continue
        om = re.match(r'^\s*([A-D])\)\s*(.+)', line)
        if om and current_q:
            current_q['options'][om.group(1)] = om.group(2).strip()
    return questions


def parse_answers(path):
    """解析答案文件，返回 {qnum: letter}"""
    text = path.read_text(encoding='utf-8')
    answers = {}
    for line in text.split('\n'):
        m = re.match(r'^\s*(\d+)\.\s*([A-D])', line)
        if m:
            answers[int(m.group(1))] = m.group(2)
    return answers


def parse_transcript(path):
    """解析听力原文，返回按句子分割的列表"""
    text = path.read_text(encoding='utf-8')
    text = re.sub(r'^#.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*+', '', text)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]


# ─── 分析模块 ───────────────────────────────────────────────────────────────

def get_section(qnum):
    if 1 <= qnum <= 8:
        return 'A'
    elif 9 <= qnum <= 15:
        return 'B'
    elif 16 <= qnum <= 25:
        return 'C'
    return None


def content_words(text):
    words = re.findall(r'[a-z]+', text.lower())
    return {w for w in words if w not in STOP_WORDS and len(w) >= 3}


def jaccard(set1, set2):
    if not set1 or not set2:
        return 0.0
    return len(set1 & set2) / len(set1 | set2)


def analyze_letter_distribution(all_data):
    """分析答案字母分布"""
    print("\n" + "="*60)
    print("一、答案字母分布")
    print("="*60)
    by_section = defaultdict(list)
    for item in all_data:
        by_section[item['section']].append(item['answer'])

    for sec in ['A', 'B', 'C']:
        letters = by_section[sec]
        c = Counter(letters)
        total = len(letters)
        print(f"\nSection {sec} ({total} 题):")
        for l in 'ABCD':
            print(f"  {l}: {c[l]} ({c[l]/total*100:.1f}%)")


def analyze_consecutive_avoidance(all_data):
    """分析连号回避规律"""
    print("\n" + "="*60)
    print("二、连号回避分析")
    print("="*60)
    by_exam = defaultdict(list)
    for item in all_data:
        by_exam[item['key']].append(item)

    same_count = 0
    total_pairs = 0
    triple_count = 0

    for key, items in by_exam.items():
        items.sort(key=lambda x: x['qnum'])
        for i in range(len(items) - 1):
            if items[i]['section'] == items[i+1]['section']:
                total_pairs += 1
                if items[i]['answer'] == items[i+1]['answer']:
                    same_count += 1
        for i in range(len(items) - 2):
            if (items[i]['section'] == items[i+1]['section'] == items[i+2]['section']
                and items[i]['answer'] == items[i+1]['answer'] == items[i+2]['answer']):
                triple_count += 1

    print(f"\n相邻同字母：{same_count}/{total_pairs} = {same_count/total_pairs*100:.1f}%")
    print(f"连续3题同字母：{triple_count} 次")


def analyze_pincer_constraint(all_data):
    """分析钳制约束"""
    print("\n" + "="*60)
    print("三、钳制约束（双向夹击）")
    print("="*60)
    by_exam = defaultdict(list)
    for item in all_data:
        by_exam[item['key']].append(item)

    same_neighbor_same_mid = 0
    same_neighbor_total = 0
    diff_neighbor_other = 0
    diff_neighbor_total = 0

    for key, items in by_exam.items():
        items.sort(key=lambda x: x['qnum'])
        for i in range(1, len(items) - 1):
            if not (items[i-1]['section'] == items[i]['section'] == items[i+1]['section']):
                continue
            left = items[i-1]['answer']
            mid = items[i]['answer']
            right = items[i+1]['answer']
            if left == right:
                same_neighbor_total += 1
                if mid == left:
                    same_neighbor_same_mid += 1
            else:
                diff_neighbor_total += 1
                if mid != left and mid != right:
                    diff_neighbor_other += 1

    print(f"\n两邻居相同时，中间=该字母：{same_neighbor_same_mid}/{same_neighbor_total}")
    if diff_neighbor_total:
        print(f"两邻居不同时，中间选第三字母：{diff_neighbor_other}/{diff_neighbor_total} = {diff_neighbor_other/diff_neighbor_total*100:.1f}%")


def analyze_transition_words(all_data, transcripts):
    """分析转折词与答案的关系"""
    print("\n" + "="*60)
    print("四、转折词信号分析")
    print("="*60)
    hit = 0
    total_transitions = 0

    for key, sentences in transcripts.items():
        exam_items = [d for d in all_data if d['key'] == key]
        answer_texts = [d['correct_text'] for d in exam_items]
        answer_words_list = [content_words(t) for t in answer_texts]

        for i, sent in enumerate(sentences):
            if TRANSITION_WORDS.search(sent):
                total_transitions += 1
                window = sentences[max(0, i-1):i+2]
                window_text = ' '.join(window).lower()
                for aw in answer_words_list:
                    overlap = sum(1 for w in aw if w in window_text)
                    if overlap >= 2:
                        hit += 1
                        break

    if total_transitions:
        print(f"\n含转折词的句子：{total_transitions}")
        print(f"±1句窗口内有答案关键词：{hit}")
        print(f"精确率：{hit/total_transitions*100:.1f}%")


def analyze_twin_strategy(all_data):
    """分析双胞胎策略（选项聚类）"""
    print("\n" + "="*60)
    print("五、双胞胎策略（最相似对包含答案）")
    print("="*60)
    by_section = defaultdict(lambda: {'hit': 0, 'total': 0})

    for item in all_data:
        options = item.get('options', {})
        if len(options) < 4:
            continue
        opt_words = {k: content_words(v) for k, v in options.items()}
        max_j = 0
        max_pair = None
        for (k1, w1), (k2, w2) in combinations(opt_words.items(), 2):
            j = jaccard(w1, w2)
            if j > max_j:
                max_j = j
                max_pair = (k1, k2)
        if max_j > 0 and max_pair:
            sec = item['section']
            by_section[sec]['total'] += 1
            if item['answer'] in max_pair:
                by_section[sec]['hit'] += 1

    total_hit = sum(v['hit'] for v in by_section.values())
    total_all = sum(v['total'] for v in by_section.values())
    print(f"\n{'Section':<10} {'命中':<8} {'总数':<8} {'命中率':<10}")
    for sec in ['A', 'B', 'C']:
        d = by_section[sec]
        if d['total']:
            print(f"{sec:<10} {d['hit']:<8} {d['total']:<8} {d['hit']/d['total']*100:.1f}%")
    if total_all:
        print(f"{'总计':<10} {total_hit:<8} {total_all:<8} {total_hit/total_all*100:.1f}%")


def analyze_outlier(all_data):
    """分析离群选项排除法"""
    print("\n" + "="*60)
    print("六、离群选项排除法")
    print("="*60)
    by_section = defaultdict(lambda: {'hit': 0, 'total': 0})

    for item in all_data:
        options = item.get('options', {})
        if len(options) < 4:
            continue
        opt_words = {k: content_words(v) for k, v in options.items()}
        avg_sim = {}
        for k1 in opt_words:
            sims = [jaccard(opt_words[k1], opt_words[k2]) for k2 in opt_words if k2 != k1]
            avg_sim[k1] = statistics.mean(sims) if sims else 0
        outlier = min(avg_sim, key=avg_sim.get)
        sec = item['section']
        by_section[sec]['total'] += 1
        if item['answer'] == outlier:
            by_section[sec]['hit'] += 1

    print(f"\n{'Section':<10} {'离群=答案':<12} {'总数':<8} {'比率':<10}")
    for sec in ['A', 'B', 'C']:
        d = by_section[sec]
        if d['total']:
            print(f"{sec:<10} {d['hit']:<12} {d['total']:<8} {d['hit']/d['total']*100:.1f}%")


def analyze_absolute_words(all_data):
    """分析绝对化表述"""
    print("\n" + "="*60)
    print("七、绝对化表述排除法验证")
    print("="*60)
    has_absolute_correct = 0
    has_absolute_total = 0

    for item in all_data:
        options = item.get('options', {})
        for letter, text in options.items():
            if ABSOLUTE_WORDS.search(text):
                has_absolute_total += 1
                if letter == item['answer']:
                    has_absolute_correct += 1

    if has_absolute_total:
        print(f"\n含绝对化词的选项总数：{has_absolute_total}")
        print(f"其中为正确答案：{has_absolute_correct}")
        print(f"正确率：{has_absolute_correct/has_absolute_total*100:.1f}%（基线25%）")


def analyze_option_length(all_data):
    """分析选项长度与正确率"""
    print("\n" + "="*60)
    print("八、选项长度规律")
    print("="*60)
    by_section = defaultdict(lambda: {'longest': 0, 'shortest': 0, 'mid': 0, 'total': 0})

    for item in all_data:
        options = item.get('options', {})
        if len(options) < 4:
            continue
        lengths = {k: len(v.split()) for k, v in options.items()}
        max_len = max(lengths.values())
        min_len = min(lengths.values())
        sec = item['section']
        by_section[sec]['total'] += 1
        ans_len = lengths.get(item['answer'], 0)
        if ans_len == max_len:
            by_section[sec]['longest'] += 1
        elif ans_len == min_len:
            by_section[sec]['shortest'] += 1
        else:
            by_section[sec]['mid'] += 1

    print(f"\n{'Section':<8} {'最长=答案':<12} {'最短=答案':<12} {'中等=答案':<12}")
    for sec in ['A', 'B', 'C']:
        d = by_section[sec]
        if d['total']:
            t = d['total']
            print(f"{sec:<8} {d['longest']}/{t}={d['longest']/t*100:.1f}%  "
                  f"{d['shortest']}/{t}={d['shortest']/t*100:.1f}%  "
                  f"{d['mid']}/{t}={d['mid']/t*100:.1f}%")


def analyze_section_uniformity(all_data):
    """分析 Section 内字母分布均匀程度"""
    print("\n" + "="*60)
    print("九、Section 内字母均匀分布验证")
    print("="*60)
    by_exam = defaultdict(list)
    for item in all_data:
        by_exam[(item['key'], item['section'])].append(item['answer'])

    ranges_real = {'A': [], 'B': [], 'C': []}
    for (key, sec), letters in by_exam.items():
        c = Counter(letters)
        counts = [c.get(l, 0) for l in 'ABCD']
        ranges_real[sec].append(max(counts) - min(counts))

    print("\n实测极差分布（极差≤1 的比例）：")
    for sec in ['A', 'B', 'C']:
        r = ranges_real[sec]
        le1 = sum(1 for x in r if x <= 1)
        print(f"  Section {sec}: {le1}/{len(r)} = {le1/len(r)*100:.1f}%")

    # Monte Carlo baseline
    print("\n蒙特卡洛随机基线（10万次模拟）：")
    for sec, n in [('A', 8), ('B', 7), ('C', 10)]:
        le1_count = 0
        for _ in range(100000):
            letters = [random.choice('ABCD') for _ in range(n)]
            c = Counter(letters)
            counts = [c.get(l, 0) for l in 'ABCD']
            if max(counts) - min(counts) <= 1:
                le1_count += 1
        print(f"  Section {sec} (n={n}): {le1_count/1000:.1f}%")


def analyze_cross_section_boundary(all_data):
    """分析跨 Section 边界的回避效应"""
    print("\n" + "="*60)
    print("十、跨 Section 边界分析")
    print("="*60)
    by_exam = defaultdict(list)
    for item in all_data:
        by_exam[item['key']].append(item)

    boundary_same = {'Q8-Q9': 0, 'Q15-Q16': 0}
    boundary_total = {'Q8-Q9': 0, 'Q15-Q16': 0}

    for key, items in by_exam.items():
        by_qnum = {it['qnum']: it['answer'] for it in items}
        if 8 in by_qnum and 9 in by_qnum:
            boundary_total['Q8-Q9'] += 1
            if by_qnum[8] == by_qnum[9]:
                boundary_same['Q8-Q9'] += 1
        if 15 in by_qnum and 16 in by_qnum:
            boundary_total['Q15-Q16'] += 1
            if by_qnum[15] == by_qnum[16]:
                boundary_same['Q15-Q16'] += 1

    for b in ['Q8-Q9', 'Q15-Q16']:
        if boundary_total[b]:
            print(f"\n{b}: {boundary_same[b]}/{boundary_total[b]} = {boundary_same[b]/boundary_total[b]*100:.2f}%")


def analyze_k_known_inference(all_data):
    """分析已知 k 题后的后验收窄"""
    print("\n" + "="*60)
    print("十一、递归推断验证（前3题全不同→第4题）")
    print("="*60)
    by_exam_sec = defaultdict(list)
    for item in all_data:
        by_exam_sec[(item['key'], item['section'])].append(item)

    hit = 0
    total = 0
    for (key, sec), items in by_exam_sec.items():
        items.sort(key=lambda x: x['qnum'])
        if len(items) < 4:
            continue
        first3 = [it['answer'] for it in items[:3]]
        if len(set(first3)) == 3:
            total += 1
            missing = [l for l in 'ABCD' if l not in first3][0]
            if items[3]['answer'] == missing:
                hit += 1

    if total:
        print(f"\n前3题全不同的样本数：{total}")
        print(f"第4题=缺失字母：{hit}/{total} = {hit/total*100:.1f}%")


def analyze_temporal_stability(all_data):
    """时间稳健性检验"""
    print("\n" + "="*60)
    print("十二、时间稳健性检验（2016-2020 vs 2021-2025）")
    print("="*60)
    early = [d for d in all_data if d['year'] <= 2020]
    late = [d for d in all_data if d['year'] > 2020]

    for label, subset in [('2016-2020', early), ('2021-2025', late)]:
        c = Counter(d['answer'] for d in subset)
        total = len(subset)
        print(f"\n{label} ({total} 题):")
        for l in 'ABCD':
            print(f"  {l}: {c[l]/total*100:.1f}%")


def main():
    print("CET-6 听力真题数据分析")
    print("=" * 60)

    exam_sets = find_exam_sets()
    print(f"\n找到 {len(exam_sets)} 套有效题目集")

    all_data = []
    transcripts = {}

    for key, paths in sorted(exam_sets.items()):
        questions = parse_stem(paths['stem'])
        answers = parse_answers(paths['answer'])
        sentences = parse_transcript(paths['transcript'])
        transcripts[key] = sentences

        year_match = re.match(r'(\d{4})', key)
        year = int(year_match.group(1)) if year_match else 0

        for q in questions:
            qnum = q['qnum']
            if qnum not in answers:
                continue
            sec = get_section(qnum)
            if not sec:
                continue
            ans_letter = answers[qnum]
            correct_text = q['options'].get(ans_letter, '')
            all_data.append({
                'key': key,
                'year': year,
                'qnum': qnum,
                'section': sec,
                'answer': ans_letter,
                'correct_text': correct_text,
                'options': q['options'],
            })

    print(f"有效题目总数：{len(all_data)}")

    analyze_letter_distribution(all_data)
    analyze_consecutive_avoidance(all_data)
    analyze_pincer_constraint(all_data)
    analyze_transition_words(all_data, transcripts)
    analyze_twin_strategy(all_data)
    analyze_outlier(all_data)
    analyze_absolute_words(all_data)
    analyze_option_length(all_data)
    analyze_section_uniformity(all_data)
    analyze_cross_section_boundary(all_data)
    analyze_k_known_inference(all_data)
    analyze_temporal_stability(all_data)

    print("\n" + "="*60)
    print("分析完成")


if __name__ == '__main__':
    main()
