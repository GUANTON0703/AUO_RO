const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const test = require("node:test");

const source = fs.readFileSync(
  path.join(__dirname, "../../web/js/screen-build.js"),
  "utf8",
);
const context = {
  window: {},
  Screens: {},
  App: {},
  S: {},
  esc: (value) => String(value ?? ""),
  view: () => null,
};
vm.runInNewContext(source, context);

const skillView = context.window.ROSkillView;

test("groups visible skills into novice, first, and second tier sections", () => {
  const jobs = {
    novice: { tier: "novice" },
    swordman: { tier: "first", parent_id: "novice" },
    knight: { tier: "second", parent_id: "swordman" },
  };
  const skills = [
    { id: "bash", job_id: "swordman" },
    { id: "basic", job_id: "novice" },
    { id: "pierce", job_id: "knight" },
  ];

  assert.deepEqual(
    JSON.parse(JSON.stringify(skillView.groupSkillsByTier(skills, jobs, "knight"))),
    [
      { tier: "novice", label: "新手技能", open: false, skills: [skills[1]] },
      { tier: "first", label: "一轉技能", open: false, skills: [skills[0]] },
      { tier: "second", label: "二轉技能", open: true, skills: [skills[2]] },
    ],
  );
});

test("marks a skill locked when any requires level is not learned", () => {
  const state = skillView.getSkillPrerequisiteState(
    { requires: { bash: 3, provoke: 1 } },
    { bash: 2, provoke: 1 },
  );

  assert.equal(state.met, false);
  assert.deepEqual(
    JSON.parse(JSON.stringify(state.unmet)),
    [{ id: "bash", required: 3, current: 2 }],
  );
});
