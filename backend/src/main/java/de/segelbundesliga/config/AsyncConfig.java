package de.segelbundesliga.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableAsync;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;

import java.util.concurrent.Executor;

@Configuration
@EnableAsync
public class AsyncConfig {

    /**
     * Executor for optimization tasks.
     * Limited pool size since optimizations are CPU-intensive.
     */
    @Bean(name = "optimizerExecutor")
    public Executor optimizerExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(2);
        executor.setMaxPoolSize(4);
        executor.setQueueCapacity(10);
        executor.setThreadNamePrefix("optimizer-");
        executor.setRejectedExecutionHandler((r, e) -> {
            throw new RuntimeException("Optimizer queue is full. Please try again later.");
        });
        executor.initialize();
        return executor;
    }
}
