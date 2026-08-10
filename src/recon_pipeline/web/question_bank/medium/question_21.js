window.questionBank = window.questionBank || {};
window.questionBank.medium = window.questionBank.medium || [];
window.questionBank.medium.push(
  { id:21, title:"分布式系统的一致性问题", domain:"计算机", difficulty:"中", diffClass:"is-moderate",
    summary:"CAP定理指出分布式系统在网络分区时只能在一致性和可用性中选一个，Raft算法通过领导选举和日志复制实现强一致性。",
    quickQs:["CAP定理的三选二困境","Raft算法如何保证一致性","给我出道练习题","用通俗语言解释"],
    content:`<p>当你用微信给朋友发消息时，消息经过了多少台服务器？现代互联网服务都是由成百上千台服务器组成的<strong>分布式系统</strong>。但这些服务器之间网络可能会出故障（分区），这时候系统该怎么应对？这就是分布式系统理论中最核心的问题。</p>
<h3>CAP定理：不可能三角</h3>
<p>2000年Eric Brewer提出CAP定理：一个分布式系统不可能同时满足以下三项：</p>
<ul style="padding-left:20px;">
<li><strong>一致性(C)</strong>：任何时候所有节点看到的数据一致</li>
<li><strong>可用性(A)</strong>：每个请求都能收到（非错误）响应</li>
<li><strong>分区容忍性(P)</strong>：网络分区（部分节点失联）时系统仍能工作</li>
</ul>
<p>现实中的网络分区不可避免，所以实际上是在 CP 和 AP 之间选择：银行系统选CP（宁可暂停也不能账错），社交动态feed选AP（暂时看到旧数据也比完全不能用好）。</p>
<h3>Raft共识算法：如何达成一致</h3>
<p>当多个节点需要就某个值达成一致时（如"当前leader是谁"），就需要<strong>共识算法</strong>。Raft是近年来最受欢迎的一种，因为它比经典的Paxos算法更容易理解：</p>
<div class="formula-block"><span class="formula-label">Raft的三个子问题</span>
<b>1. 领导选举</b>：Leader故障时 Followers 发起投票，获多数票者当选<br>
<b>2. 日志复制</b>：Leader 把操作日志复制给多数 Follower 后才提交<br>
<b>3. 安全性</b>：已提交日志绝不丢失（多数票保证）</div>
<p>关键洞察：选举需多数票，已提交日志至少存于多数节点——两个多数集合必有交集，所以新Leader必然包含所有已提交日志。这保证了数据不丢、状态一致。</p>
<h3>不是只有 CP 和 AP：一致性的光谱</h3>
<p>现实中系统落在"强一致"到"最终一致"之间的连续谱上，并非简单的二选一。例如 ZooKeeper 提供线性一致的协调服务（宁可牺牲一点可用性也要强一致），而 DynamoDB、Cassandra 采用<strong>最终一致性</strong>：写入可立即返回，各副本在后台慢慢追上，适合海量高并发场景。</p>
<h3>更难的挑战：拜占庭容错</h3>
<p>如果节点不只是掉线、还会<strong>故意撒谎</strong>（被黑客控制或主动作恶），就需要<strong>拜占庭容错</strong>共识（如 PBFT）。区块链正是用 PoW/PoS 这类机制，在完全互不信任的节点间达成一致——代价是惊人的算力或能源开销。Raft 假设节点"崩溃但诚实"，而拜占庭容错要应对"既崩溃又撒谎"，难度陡增。</p>`,
    quiz:[{ question:"网络分区必然存在时，分布式系统无法同时保证的是？", options:["A. 一致性与可用性","B. 一致性与分区容忍","C. 可用性与分区容忍","D. 三者都无法保证"], answerIndex:0 },
           { question:"在Raft算法中，一条日志条目被标记为committed（已提交）的条件是什么？", options:["A. Leader刚写入日志","B. 已复制到多数Follower","C. Leader应用到状态机","D. 所有Follower确认收到"], answerIndex:1 }] }
);
