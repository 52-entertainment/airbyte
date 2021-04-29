/*
 * MIT License
 *
 * Copyright (c) 2020 Airbyte
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

package io.airbyte.workers.temporal;

import io.temporal.client.WorkflowClient;
import io.temporal.testing.TestWorkflowEnvironment;
import io.temporal.worker.Worker;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;

// based of example in temporal samples:
// https://github.com/temporalio/samples-java/blob/master/src/test/java/io/temporal/samples/hello/HelloActivityTest.java
class SyncWorkflowTest {

  private static final String TASK_QUEUE = TemporalJobType.SYNC.name();

  private TestWorkflowEnvironment testEnv;
  private Worker worker;
  private WorkflowClient client;

  @BeforeEach
  public void setUp() {
    testEnv = TestWorkflowEnvironment.newInstance();
    worker = testEnv.newWorker(TASK_QUEUE);
    worker.registerWorkflowImplementationTypes(SyncWorkflow.class);

    client = testEnv.getWorkflowClient();
  }

  // @Test
  // void test() {
  // worker.registerActivitiesImplementations(new SyncWorkflow.WorkflowImpl());
  // testEnv.start();
  //
  // final SyncWorkflow workflow = client.newWorkflowStub(SyncWorkflow.class,
  // WorkflowOptions.newBuilder().setTaskQueue(TASK_QUEUE).build());
  //// workflow.run()
  // }

  @AfterEach
  public void tearDown() {
    testEnv.close();
  }

}
