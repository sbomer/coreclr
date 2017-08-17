import org.dotnet.ci.pipelines.Pipeline



class CoreclrJob {
    enum Configuration {
        debug, checked, release
    }
    enum Platform {
        debian8_4,
        osx10_12,
        windows_nt,
        freebsd,
        centos7_1,
        opensuse42_1,
        rhel7_2,
        ubuntu16_04,
        ubuntu16_10,
        fedora24,
        tizen        
    }
    enum Architecture {
        x86,
        x64
    }
    class TriggerType {
        
    }

    Platform os
    Architecture arch
    Configuration config
}


// for the generated job definitions:
// call createPipeline with the path to the file
// call trigger functions, passing trigger phrase
// maybe override some options (like the job name...)

// dotnet-ci does the following:
// createPipeline makes a Pipeline with context, baseJobName, pipelinefile
//   adds github scm (project, branch, credentialsid)
//   create standard pipeline job
//     enable concurrent build, quiet period of 5 seconds
//     wrap with timestamps, preBuild cleanup, postBuild cleanup
//   emitScmForNonPR, etc.,
//   newJob.with parameters. params become parameters of the job

def buildPipeline = Pipeline.createPipeline(this, 'buildpipeline/build-pipeline.groovy')
buildPipeline.triggerPipelineManually()
buildPipeline.triggerPipelineOnPush()
buildPipeline.triggerPipelineOnEveryGithubPR('build pipeline status', ".*test\\W+my\\W+job.*")

def testPipeline = Pipeline.createPipeline(this, 'buildpipeline/test-pipeline.groovy')
testPipeline.triggerPipelineManually([os: "Windows_NT"])
testPipeline.triggerPipelineManually([os: "Ubuntu"])

def jitdiffPipeline = Pipeline.createPipeline(this, 'buildpipeline/jitdiff-pipeline.groovy')
jitdiffPipeline.triggerPipelineManually([os: "Windows_NT"])
jitdiffPipeline.triggerPipelineManually([os: "Ubuntu"])



[''].each { configuration ->
    testPipeline.triggerPipelineManually(['Configuration':configuration])
}
              
