window.questionBank = window.questionBank || {};
window.questionBank.easy = window.questionBank.easy || [];
window.questionBank.easy.push(
  { id:5, title:"进程调度与并发控制", domain:"计算机", difficulty:"低", diffClass:"is-low",
    summary:"操作系统需要同时管理多个程序运行，调度算法决定谁先用CPU，并发机制防止多个程序互相干扰。",
    quickQs:["各种调度算法的对比","死锁是怎么产生的","给我出道练习题","用通俗语言解释"],
    content:`<p>你的电脑同时运行着浏览器、音乐播放器和后台更新——但CPU一次只能执行一个程序。操作系统扮演"交通指挥官"的角色，快速切换让每个程序都有机会运行，这叫做<strong>进程调度</strong>。调度算法决定了切换的策略，直接影响电脑的响应速度和使用体验。</p>
<h3>常见调度算法</h3>
<table class="data-table">
<tr><th>算法</th><th>策略</th><th>优点</th><th>缺点</th></tr>
<tr><td>FCFS<br>(先来先服务)</td><td>排队，先到的先执行</td><td>简单公平</td><td>一个长任务卡住所有人</td></tr>
<tr><td>SJF<br>(最短优先)</td><td>先执行耗时最短的</td><td>平均等待时间最短</td><td>需要预知执行时间</td></tr>
<tr><td>RR<br>(时间片轮转)</td><td>每人轮流用一小段时间片</td><td>响应快，感觉"同时"运行</td><td>频繁切换有开销</td></tr>
<tr><td>MLFQ<br>(多级反馈队列)</td><td>新任务优先级高<br>用久了降级</td><td>自适应，兼顾各类任务</td><td>实现复杂</td></tr>
</table>
<h3>并发问题：当程序抢资源时</h3>
<p>如果两个程序同时写同一个文件，内容可能乱套。这种竞争共享资源的情况叫做<strong>竞态条件</strong>。解决方法是使用<strong>锁</strong>：程序访问共享资源前先"上锁"，用完后再"解锁"。但如果程序A拿着锁1等锁2，程序B拿着锁2等锁1，两人互相等对方释放——这就形成了<strong>死锁</strong>，两个程序都卡死了。预防死锁是操作系统设计中的重要课题。</p>`,
    quiz:[{ question:"时间片轮转(RR)调度的主要优点是？", options:["A. 平均等待时间最短","B. 响应快、交互体验好","C. 不需要任何上下文切换开销","D. 适合批处理任务"], answerIndex:1 },
           { question:"两个线程互相持有对方需要的锁并无限等待，这种现象叫什么？", options:["A. 竞态条件","B. 死锁","C. 饥饿","D. 活锁"], answerIndex:1 }] }
);
