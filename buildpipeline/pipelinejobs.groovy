import org.dotnet.ci.pipelines.Pipeline

def testPipeline = Pipeline.createPipeline(this, 'buildpipeline/test-pipeline.groovy')
testPipeline.triggerPipelineManually()
testPipeline.triggerPipelineOnPush()
testPipeline.triggerPipelineOnEveryGithubPR('test pipeline status', ".*test\\W+my\\W+job.*")

def testPipeline2 = Pipeline.createPipeline(this, 'buildpipeline/test-pipeline2.groovy')
testPipeline2.triggerPipelineManually()
