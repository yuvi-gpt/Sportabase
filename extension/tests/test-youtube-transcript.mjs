import assert from "node:assert/strict";

import {
  normalizeTranscriptSegments,
} from "../src/content/youtube-transcript.testable.mjs";


function testNormalTranscript() {
  const segments = [
    "Mercedes showed strong race pace throughout the opening stint and maintained competitive lap times against the leading cars.",
    "Russell qualified on the front row after improving considerably during the final qualifying session.",
    "Tyre degradation remained controlled during the longest run despite unusually high track temperatures.",
    "Official timing data showed that the car gained time primarily through the medium-speed corners.",
    "The presenter compared race simulations from Mercedes, Ferrari, McLaren, and Red Bull.",
    "Pit-stop timing affected the final result, although the underlying performance remained competitive.",
    "The analysis clearly separated confirmed timing information from the presenter's personal interpretation.",
    "The final conclusion was supported by qualifying results, race pace, tyre wear, and strategy data.",
  ];

  const result =
    normalizeTranscriptSegments(
      segments.map((text) => ({
        text,
      }))
    );

  assert.equal(
    result.segmentCount,
    8
  );

  assert.equal(
    result.duplicateSegmentCount,
    0
  );

  assert.equal(
    result.extractionConfidence,
    1
  );

  assert.deepEqual(
    result.warnings,
    []
  );

  assert.equal(
    result.transcript,
    segments.join("\n")
  );
}

function testAdjacentDuplicatesAreRemoved() {
  const result = normalizeTranscriptSegments([
    { text: "Mercedes showed strong race pace." },
    { text: " Mercedes showed strong race pace! " },
    { text: "Russell delivered another podium." },
  ]);

  assert.equal(result.rawSegmentCount, 3);
  assert.equal(result.segmentCount, 2);
  assert.equal(result.duplicateSegmentCount, 1);

  assert.equal(
    result.transcript.match(
      /Mercedes showed strong race pace/g
    )?.length,
    1
  );

  assert.ok(
    result.extractionConfidence < 1
  );
}


function testNonAdjacentRepeatedStatementsRemain() {
  const result = normalizeTranscriptSegments([
    { text: "Mercedes led the race." },
    { text: "The strategy changed after the stop." },
    { text: "Mercedes led the race." },
  ]);

  assert.equal(result.segmentCount, 3);
  assert.equal(result.duplicateSegmentCount, 0);
}


function testEmptySegmentsAreRemoved() {
  const result = normalizeTranscriptSegments([
    { text: "" },
    { text: "   " },
    { text: "A valid caption remains." },
  ]);

  assert.equal(result.emptySegmentCount, 2);
  assert.equal(result.segmentCount, 1);
  assert.equal(
    result.transcript,
    "A valid caption remains."
  );

  assert.ok(
    result.warnings.includes(
      "very_few_segments"
    )
  );

  assert.ok(
    result.warnings.includes(
      "very_short_transcript"
    )
  );
}


function testFragmentedCaptionsAreFlagged() {
  const result = normalizeTranscriptSegments([
    "One",
    "two",
    "three",
    "four",
    "five",
    "six",
  ]);

  assert.ok(
    result.warnings.includes(
      "fragmented_captions"
    )
  );

  assert.ok(
    result.extractionConfidence < 0.8
  );
}


function testTimestampsArePreserved() {
  const result = normalizeTranscriptSegments([
    {
      text: "Opening claim.",
      timestamp: "0:15",
    },
    {
      text: "Supporting evidence.",
      timestamp: "1:22",
    },
  ]);

  assert.equal(
    result.segments[0].timestamp,
    "0:15"
  );

  assert.equal(
    result.segments[1].timestamp,
    "1:22"
  );
}


const tests = [
  testNormalTranscript,
  testAdjacentDuplicatesAreRemoved,
  testNonAdjacentRepeatedStatementsRemain,
  testEmptySegmentsAreRemoved,
  testFragmentedCaptionsAreFlagged,
  testTimestampsArePreserved,
];

for (const test of tests) {
  test();
  console.log(`PASS ${test.name}`);
}

console.log(
  `\nRan ${tests.length} transcript tests`
);
console.log("OK");
