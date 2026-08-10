window.questionBank = window.questionBank || {};
window.questionBank.medium = window.questionBank.medium || [];
window.questionBank.medium.push(
  { id:31, title:"二叉树结构与遍历算法", domain:"计算机", difficulty:"中", diffClass:"is-moderate",
    summary:"二叉树是每个节点最多有两个子节点的树形结构，前序、中序、后序三种基本遍历方式，以及二叉搜索树的有序特性。",
    quickQs:["三种深度优先遍历的区别","二叉搜索树的性质","给我出道练习题","用通俗语言解释"],
    content:`<p>想象一个家谱：每个人最多有两个孩子。这种"每个节点最多有两个分支"的结构就叫<strong>二叉树</strong>，是计算机科学中最基础和最常用的数据结构之一，从文件系统的目录结构到搜索引擎的索引都用到它。</p>
<h3>二叉树的定义</h3>
<p>二叉树由<strong>根节点</strong>和两棵互不相交的子树（左子树、右子树）组成，每个节点最多有两个子节点。关键是"左"和"右"是有区别的——左子树和右子树不能互换。</p>
<h3>三种深度优先遍历</h3>
<p>"遍历"就是按某种顺序访问树中所有节点。根据"根节点在什么时候被访问"，有三种经典方式：</p>
<div class="formula-block"><span class="formula-label">遍历顺序规则</span>
<strong>前序</strong>：先访问根，再左子树，再右子树（根→左→右）<br>
<strong>中序</strong>：先左子树，再根，再右子树（左→根→右）<br>
<strong>后序</strong>：先左子树，再右子树，最后根（左→右→根）</div>
<p>以表达式树为例：中序遍历得到标准的中缀表达式，后序遍历得到计算机更容易计算的后缀（逆波兰）表达式。</p>
<h3>二叉搜索树（BST）：有序的二叉树</h3>
<p>BST是一种特殊的二叉树，满足一条简单却强大的规则：</p>
<div class="formula-block"><span class="formula-label">BST性质</span>
对于任一节点：<br>
左子树所有节点的值 &lt; 该节点值 &lt; 右子树所有节点的值</div>
<p>这条性质带来一个惊人的后果：<strong>对BST做中序遍历，得到的节点序列是严格升序排列的</strong>！这也是很多排序和查找算法（如快速排序的分区思想）的底层逻辑。在平衡的BST中，查找、插入、删除操作的平均时间复杂度都是 O(log n)，非常高效。</p>`,
    quiz:[{ question:"二叉搜索树(BST)的中序遍历结果具有什么特点？", options:["A. 随机顺序","B. 升序排列","C. 降序排列","D. 层次顺序"], answerIndex:1 },
           { question:"二叉树的前序遍历顺序是什么？", options:["A. 根→左→右","B. 左→根→右","C. 左→右→根","D. 左→右→根（同后序）"], answerIndex:0 }] }
);
