/**
 * 工期预估 Excel 生成器
 * 用法: node generate-estimate.js --name "迭代名称" --output "输出路径.xlsx" --data "数据JSON路径"
 * 
 * 数据JSON格式见下方 DATA_TEMPLATE
 */
const XLSX = require('xlsx');
const path = require('path');
const fs = require('fs');

// 解析命令行参数
const args = process.argv.slice(2);
function getArg(name, defaultVal) {
  const idx = args.indexOf(`--${name}`);
  return idx !== -1 && args[idx + 1] ? args[idx + 1] : defaultVal;
}

const projectName = getArg('name', '项目工期预估');
const outputPath = getArg('output', path.join(__dirname, '..', '工期预估.xlsx'));
const dataPath = getArg('data', null);

// 加载数据
let data;
if (dataPath && fs.existsSync(dataPath)) {
  data = JSON.parse(fs.readFileSync(dataPath, 'utf-8'));
} else {
  // 使用内置示例数据（可被 --data 参数覆盖）
  data = {
    projectInfo: {
      name: projectName,
      scope: '用户端（Web + H5）',
      featureCount: '待填写',
      excluded: '无改动',
    },
    roles: [
      { name: '产品经理', items: [
        { task: '评审整合', days: 1 },
        { task: '交互设计确认 + 原型验收', days: 0.5 },
        { task: '验收标准 + 验收用例', days: 1 },
        { task: 'UAT 验收 + 问题跟踪', days: 0.5 },
      ]},
      { name: 'UED设计师', items: [
        { task: '页面设计（Web+H5）', days: 2 },
        { task: '标注交付 + 设计走查', days: 0.5 },
      ]},
      { name: '后端开发', items: [
        { task: 'DB变更', complexity: '中', days: 1 },
        { task: 'API开发', complexity: '中', days: 3 },
        { task: '联调 + 自测', complexity: '-', days: 1.5 },
      ]},
      { name: '前端-Web', items: [
        { task: '页面开发', complexity: '高', days: 4 },
        { task: '联调 + 自测', complexity: '-', days: 1 },
      ]},
      { name: '前端-H5', items: [
        { task: '页面开发（移动端适配）', complexity: '高', days: 4.5 },
        { task: '联调 + 自测', complexity: '-', days: 1.5 },
      ]},
      { name: 'QA测试', items: [
        { task: '测试用例编写', days: 1.5 },
        { task: '功能测试', days: 2 },
        { task: '跨端测试', days: 0.5 },
        { task: '回归测试', days: 1 },
        { task: 'Bug验证 + UAT配合', days: 1 },
      ]},
    ],
    risks: [
      { name: '示例风险', level: '高', impact: '示例影响', mitigation: '示例应对' },
    ],
    cycleEstimate: {
      parallel: '约3~3.5周',
      compressed: '若Web/H5同一组前端，可压缩至约2.5~3周',
    },
  };
}

// ========== 生成 Excel ==========
const wb = XLSX.utils.book_new();

// Sheet 1: 总览
const overviewRows = [
  [data.projectInfo.name + ' · 全角色工期预估'],
  [],
  ['项目信息'],
  ['迭代名称', data.projectInfo.name],
  ['涉及端', data.projectInfo.scope],
  ['功能点数', data.projectInfo.featureCount],
  ['运营端/渠道端', data.projectInfo.excluded],
  [],
  ['角色总览', '人天', '占比'],
];

const totalDays = data.roles.reduce((sum, r) => sum + r.items.reduce((s, i) => s + i.days, 0), 0);
data.roles.forEach(r => {
  const days = r.items.reduce((s, i) => s + i.days, 0);
  overviewRows.push([r.name, days, ((days / totalDays) * 100).toFixed(1) + '%']);
});
overviewRows.push(['合计', totalDays, '100%']);
overviewRows.push([]);
overviewRows.push(['自然日周期（并行）', data.cycleEstimate.parallel]);
if (data.cycleEstimate.compressed) {
  overviewRows.push(['压缩周期', data.cycleEstimate.compressed]);
}

const ws1 = XLSX.utils.aoa_to_sheet(overviewRows);
ws1['!cols'] = [{ wch: 42 }, { wch: 12 }, { wch: 10 }];
XLSX.utils.book_append_sheet(wb, ws1, '总览');

// 各角色 Sheet
data.roles.forEach(role => {
  const hasComplexity = role.items.some(i => i.complexity);
  const headers = hasComplexity ? ['工作项', '复杂度', '人天'] : ['工作项', '人天'];
  const rows = [headers];
  let subtotal = 0;
  role.items.forEach(item => {
    if (hasComplexity) {
      rows.push([item.task, item.complexity || '-', item.days]);
    } else {
      rows.push([item.task, item.days]);
    }
    subtotal += item.days;
  });
  rows.push(hasComplexity ? ['小计', '', subtotal] : ['小计', subtotal]);

  const ws = XLSX.utils.aoa_to_sheet(rows);
  ws['!cols'] = hasComplexity
    ? [{ wch: 65 }, { wch: 10 }, { wch: 10 }]
    : [{ wch: 55 }, { wch: 10 }];
  // Sheet名最多31字符
  const sheetName = role.name.substring(0, 31);
  XLSX.utils.book_append_sheet(wb, ws, sheetName);
});

// 风险项 Sheet
if (data.risks && data.risks.length > 0) {
  const riskRows = [['风险项', '风险等级', '影响', '应对措施']];
  data.risks.forEach(r => {
    riskRows.push([r.name, r.level, r.impact, r.mitigation]);
  });
  const ws = XLSX.utils.aoa_to_sheet(riskRows);
  ws['!cols'] = [{ wch: 30 }, { wch: 10 }, { wch: 30 }, { wch: 40 }];
  XLSX.utils.book_append_sheet(wb, ws, '风险项');
}

// 写入文件
const dir = path.dirname(outputPath);
if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
XLSX.writeFile(wb, outputPath);
console.log('Excel generated:', outputPath);
