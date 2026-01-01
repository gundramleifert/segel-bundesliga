package gundramleifert.pairing_list.cost_calculators;

import gundramleifert.pairing_list.MatchMatrix;
import gundramleifert.pairing_list.configs.OptMatchMatrixConfig;
import gundramleifert.pairing_list.configs.ScheduleConfig;
import gundramleifert.pairing_list.types.Flight;
import gundramleifert.pairing_list.types.Race;
import gundramleifert.pairing_list.types.Schedule;

public class CostCalculatorMatchMatrix implements ICostCalculator {

  private final ScheduleConfig properties;
  private final OptMatchMatrixConfig optConfig;

  public CostCalculatorMatchMatrix() {
    this(null, null);
  }

  public CostCalculatorMatchMatrix(ScheduleConfig properties, OptMatchMatrixConfig optConfig) {
    this.properties = properties;
    this.optConfig = optConfig;
  }

  public double score(MatchMatrix matchMatrix) {
    double res = 0;
    double avg = matchMatrix.avg();
    for (int i = 0; i < matchMatrix.mat.length; i++) {
      byte[] vec = matchMatrix.mat[i];
      for (int j = 0; j < i; j++) {
        double diff = vec[j] - avg;
        res += Math.abs(diff * diff * diff);
      }
    }
    double v = matchMatrix.avgLowerParticipants();
    if (v > 0.0) {
      double res2 = 0;
      for (int i = 0; i < matchMatrix.lowerParticipants.length; i++) {
        double diff = v - matchMatrix.lowerParticipants[i];
        res2 += Math.abs(diff * diff * diff);
      }
      res += res2 * optConfig.factorLessParticipants;
    }
    return res;
  }

  public double score(Schedule schedule) {
    double score = score(schedule.getMatchMatrix());
    if (!this.properties.isFull && optConfig.factorTeamMissing > 0.0) {
      Flight flight = schedule.lastFlight();
      int min = 100;
      int max = 0;
      for (Race race : flight.races) {
        int cnt = 0;
        for (byte team : race.teams) {
          if (team >= properties.numTeams) {
            cnt++;
          }
        }
        min = Math.min(min, cnt);
        max = Math.max(max, cnt);
      }
      score += (max - min) * optConfig.factorTeamMissing;
    }
    return score;
  }
}
