const slides = (() => {
  const groups = window.questionBank || {};
  const specifications = [
    { key: "easy", label: "低", count: 16 },
    { key: "medium", label: "中", count: 16 },
    { key: "hard", label: "高", count: 16 },
  ];
  const merged = [];

  for (const specification of specifications) {
    const questions = groups[specification.key];
    if (!Array.isArray(questions)) {
      throw new Error(`题库加载失败：缺少 ${specification.key} 难度文件`);
    }
    if (questions.length !== specification.count) {
      throw new Error(
        `题库加载失败：${specification.label}难度应有 ${specification.count} 题，实际 ${questions.length} 题`,
      );
    }
    for (const question of questions) {
      if (question.difficulty !== specification.label) {
        throw new Error(`题库加载失败：题目 ${question.id} 的难度标签不匹配`);
      }
      merged.push(question);
    }
  }

  merged.sort((left, right) => left.id - right.id);
  const ids = new Set(merged.map((question) => question.id));
  if (merged.length !== 48 || ids.size !== 48) {
    throw new Error("题库加载失败：必须包含 48 个不重复题目");
  }
  return Object.freeze(merged);
})();

