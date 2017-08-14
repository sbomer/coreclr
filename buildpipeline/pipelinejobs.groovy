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



def buildPipeline = Pipeline.createPipeline(this, 'buildpipeline/build-pipeline.groovy')
buildPipeline.triggerPipelineManually()
buildPipeline.triggerPipelineOnPush()
buildPipeline.triggerPipelineOnEveryGithubPR('build pipeline status', ".*test\\W+my\\W+job.*")

def testPipeline = Pipeline.createPipeline(this, 'buildpipeline/test-pipeline.groovy')
testPipeline.triggerPipelineManually()

def jitdiffPipeline = Pipeline.createPipeline(this, 'buildpipeline/jitdiff-pipeline.groovy')




[''].each { configuration ->
    testPipeline2.triggerPipelineManually(['Configuration':configuration])
}
